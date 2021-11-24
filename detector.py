import requests


class Detector:

    def __init__(self, token, repository, commit):
        self.token = token
        self.repository = repository
        self.commit = commit
        self.commits = None
        self.ignored_commits = {}

    def mark_fix_and_get_defects(self, commits):
        print(self.get_rate())
        self.commits = commits
        fix_defects = set()
        ci_defects = set()
        too_comprehensive_list = []
        for sha, commit in self.commits.items():
            if is_message_fix(commit.get("message").lower()):
                commit.add("is_fix", True)
                if commit.get("file_count") > 1:
                    too_comprehensive_list.append(sha)
                    continue
                defect = self.find_defect_source(commit)
                if defect is not None:
                    fix_defects.add(defect)
            else:
                commit.add("is_fix", False)
        print(self.get_rate())

        is_previous_fail = False
        for sha, commit in self.commits.items():
            # TODO: improvement for later: if a test is fuzzy (fails sometimes),
            # ignore the test and check all statuses without it again
            if not is_previous_fail and commit.get("ci_state") == "failure":
                ci_defects.add(sha)
                is_previous_fail = True
            if commit.get("ci_state") != "failure":
                is_previous_fail = False
        fix_defect_list = [(sha in fix_defects) for sha in self.commits]
        print(f"Defects recognized from blame: {fix_defect_list.count(True)}")
        ci_defect_list = [(sha in ci_defects) for sha in self.commits]
        print(f"Defects recognized from failing pipelines: {ci_defect_list.count(True)}")
        doubly_defect_list = [((sha in fix_defects) and (sha in ci_defects)) for sha in self.commits]
        print(f"Defects from blame and failing pipelines: {doubly_defect_list.count(True)}")
        defect_list = [((sha in fix_defects) or (sha in ci_defects)) for sha in self.commits]
        return defect_list

    def find_defect_source(self, commit):
        # scan backwards to find possible defects: no defect can have been fixed before it was introduced
        blame_list = self.git_blame(commit.get("sha"), commit.get("files")[0].filename)
        overwrite_distribution = {}
        previous_blame_sha = None
        blame_score = 0  # blame_score is double the count of lines changed in a range (always an integer)
        for blame in blame_list:
            blame_sha = blame["commit"]["oid"]
            if blame_sha not in overwrite_distribution:
                overwrite_distribution[blame_sha] = 0
            overwrite_distribution[blame_sha] += blame_score
            blame_score = 0
            if blame_sha == commit.get("sha"):
                blame_score = blame["startingLine"] + blame["endingLine"]
                if previous_blame_sha:
                    overwrite_distribution[previous_blame_sha] += blame_score
                else:
                    blame_score *= 2
            previous_blame_sha = blame_sha
            if blame_sha not in self.commits:  # is this necessary?
                if blame_sha not in self.ignored_commits:
                    self.ignored_commits[blame_sha] = 0
                self.ignored_commits[blame_sha] += 1
                continue
        if commit.get("sha") in overwrite_distribution:
            overwrite_distribution.pop(commit.get("sha"))
        else:
            print(f"Commit {commit.get('sha')} was not a part of its own blame")
        if len(overwrite_distribution) == 0:
            return None
        return max(overwrite_distribution, key=overwrite_distribution.get)

    def git_blame(self, sha, file):
        owner = self.repository.split("/")[0]
        name = self.repository.split("/")[1]
        query = f"""
        {{
            repository(owner: "{owner}", name: "{name}") {{
                object(expression: "{sha}") {{
                    ... on Commit {{
                        blame(path: "{file}") {{
                            ranges {{
                                startingLine
                                endingLine
                                commit {{
                                    oid
                                    message
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        blame = requests.post(
            "https://api.github.com/graphql",
            headers={"Authorization": "bearer " + self.token},
            json={"query": query})
        return blame.json()["data"]["repository"]["object"]["blame"]["ranges"]

    def get_rate(self):
        query = """
        {
            rateLimit {
                limit
                cost
                remaining
                resetAt
            }
        }
        """
        remaining = requests.post(
            "https://api.github.com/graphql",
            headers={"Authorization": "bearer " + self.token},
            json={"query": query})
        return remaining.json()["data"]["rateLimit"]


def is_message_fix(msg):
    msg = msg.lower()
    fix_txt_list = ["fix", "bug", "issue", "resolve"]
    # people can write commit logs such as "fixes documentation" which would not be considered a fix for a defect
    for fix_txt in fix_txt_list:
        if fix_txt in msg:
            return True
    return False
