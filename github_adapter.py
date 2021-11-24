import math
import time
from github import Github, GithubException

from commit import Commit

COMMIT_LIMIT = 500


class GithubAdapter:
    file_exp_history = {}
    file_history = {}
    exp_history = {}
    file_detailed_history = {}

    def __init__(self, token, repository, commit_sha):
        self.g = Github(token)
        self.repo = self.g.get_repo(repository)
        self.final_commit_sha = commit_sha
        print(f"Running defect prediction for commit {commit_sha}")

    def get_features(self):
        features = {}
        print(self.g.get_rate_limit())
        if self.final_commit_sha:
            repo_head = self.repo.get_commits(self.final_commit_sha)
        else:
            repo_head = self.repo.get_commits()
        repo_commit_count = repo_head.totalCount
        commit_count_to_examine = min(repo_commit_count, COMMIT_LIMIT)
        print(f"{commit_count_to_examine} commits will be examined "
              f"(Actual: {repo_commit_count}, Limit: {COMMIT_LIMIT})")
        commit_count = 0
        for github_commit in list(repo_head[:commit_count_to_examine]).__reversed__():
            commit = self.create_commit(github_commit, commit_count)
            features[commit.get("sha")] = commit
            commit_count += 1
        print(self.g.get_rate_limit())
        return features

    def create_commit(self, gc, commit_count):
        commit = Commit()
        commit.add("sha", gc.sha)
        commit.add("index", commit_count)
        if gc.author not in self.exp_history:
            self.exp_history[gc.author] = 0
        commit.add("total_experience", self.exp_history[gc.author])
        self.exp_history[gc.author] += 1
        commit.add("additions", gc.stats.additions)
        commit.add("deletions", gc.stats.deletions)
        commit.add("changes", gc.stats.total)
        self.add_file_properties(gc, commit)
        self.add_file_exp_properties(gc, commit)
        self.add_entropy(gc, commit)
        self.add_ci_properties(gc, commit)
        commit.add("message", gc.commit.message)
        return commit

    def add_file_properties(self, gc, commit):
        commit.add("file_count", len(gc.files))
        commit.add("files", gc.files)
        total_complexity = 0
        highest_complexity = 0
        previous_changes = set()
        for file in gc.files:
            if file.previous_filename and file.previous_filename in self.file_history:
                self.file_history[file.filename] = self.file_history.pop(file.previous_filename)
                self.file_detailed_history[file.filename] = self.file_detailed_history.pop(file.previous_filename)
                for author in self.file_exp_history:
                    author_experience = self.file_exp_history[author]
                    if file.previous_filename in author_experience:
                        author_experience[file.filename] = author_experience.pop(file.previous_filename)
            if file.filename not in self.file_history:
                self.file_history[file.filename] = 0
                self.file_detailed_history[file.filename] = []
            current_complexity = self.file_history[file.filename]
            total_complexity += current_complexity
            if current_complexity > highest_complexity:
                highest_complexity = current_complexity
            previous_changes = previous_changes.union(self.file_detailed_history[file.filename])
            self.file_history[file.filename] += 1
            self.file_detailed_history[file.filename].append(gc.sha)
        avg_complexity = 0 if len(gc.files) == 0 else total_complexity / len(gc.files)
        commit.add("avg_file_complexity", avg_complexity)
        commit.add("highest_file_complexity", highest_complexity)
        commit.add("previous_change_count", len(previous_changes))

    def add_file_exp_properties(self, gc, commit):
        total_experience = 0
        lowest_experience = 0
        lowest_experience_prop = 1
        for file in gc.files:
            if gc.author not in self.file_exp_history:
                self.file_exp_history[gc.author] = {}
            if file.filename not in self.file_exp_history[gc.author]:
                self.file_exp_history[gc.author][file.filename] = 0
            current_experience = self.file_exp_history[gc.author][file.filename]
            total_experience += current_experience
            if current_experience < lowest_experience:
                lowest_experience = current_experience
            self.file_exp_history[gc.author][file.filename] += 1
            current_file_complexity = self.file_history[file.filename] - 1  # TODO: Very dependent on other function!
            current_experience_prop = 1 if current_file_complexity == 0 \
                else current_experience / current_file_complexity
            if current_experience_prop < lowest_experience_prop:
                lowest_experience_prop = current_experience_prop
        avg_experience = 0 if len(gc.files) == 0 else total_experience / len(gc.files)
        commit.add("avg_experience", avg_experience)
        commit.add("lowest_experience", lowest_experience)
        commit.add("lowest_experience_proportion", lowest_experience_prop)

    def add_entropy(self, gc, commit):
        entropy = 0
        if gc.stats.total != 0:
            for file in gc.files:
                information_ratio = file.changes / gc.stats.total
                entropy -= information_ratio * math.log2(information_ratio) if information_ratio > 0 else 0
        else:
            print(f"Found commit with no changes: {commit.get('sha')}")
        commit.add("entropy", entropy)

    def add_ci_properties(self, gc, commit):
        ci_state_dict = {"success": 0, "pending": 0, "failure": 0}
        attempts = 5
        success = False
        for i in range(attempts):
            try:
                for status in gc.get_combined_status().statuses:
                    if status.state in ["success", "fixed"]:
                        ci_state_dict["success"] += 1
                    elif status.state in ["pending", "timeout", "running", "queued", "timedout"]:
                        ci_state_dict["pending"] += 1
                    elif status.state in ["warning", "canceled", "stale", "infrastructure_fail", "action_required",
                                          "skipped", "cancelled", "neutral", "retried", "no_tests"]:
                        ci_state_dict["pending"] += 1  # TODO: Add a warning rate and split it out from pending
                    elif status.state in ["failure", "error", "failed"]:
                        ci_state_dict["failure"] += 1
                    else:
                        raise Exception(f"Unknown status state: {status.state}")
                for check_run in gc.get_check_runs():
                    if check_run.status == "queued":  # queued check runs do not have a conclusion
                        ci_state_dict["pending"] += 1
                    elif check_run.conclusion == "success":
                        ci_state_dict["success"] += 1
                    elif check_run.conclusion == "pending":
                        ci_state_dict["pending"] += 1
                    elif check_run.conclusion == "failure":
                        ci_state_dict["failure"] += 1
                    elif check_run.conclusion == "cancelled":
                        print(f"Uncovered a cancelled CI pipeline for {commit.get('sha')}")
                    else:
                        raise Exception(f"Unknown check run state: {check_run.conclusion}")
                commit.add("ci_count", gc.get_combined_status().total_count + gc.get_check_runs().totalCount)
                success = True
            except GithubException as e:
                print(f"Attempt {i + 1} for commit {commit.get('sha')}: There was a github server error: {e}")
                time.sleep(i + 1)
            if success:
                break
        if not success:
            raise Exception(f"Failed to get commit {commit.get('sha')}")
        commit.add("ci_state", "failure" if ci_state_dict["failure"] > 0
                               else "pending" if ci_state_dict["pending"] > 0 else "success")

        commit.add("pending_rate", ci_state_dict["pending"] / sum(ci_state_dict.values())
                   if sum(ci_state_dict.values()) > 0 else 0)
        commit.add("failure_rate", ci_state_dict["failure"] / (ci_state_dict["success"] + ci_state_dict["failure"])
                   if ci_state_dict["failure"] > 0 else 0)
