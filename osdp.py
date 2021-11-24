import os
import csv
from datetime import datetime

from detector import Detector
from estimator import Estimator
from github_adapter import GithubAdapter

TOKEN = os.environ.get("TOKEN", None)
REPOSITORY = os.environ.get("REPOSITORY", None)
COMMIT_SHA = os.environ.get("COMMIT_SHA", None)
if os.path.isfile(".env"):
    with open(".env") as fp:
        for line in fp.readlines():
            line = line.strip().split("=", 1)
            if TOKEN is None and line[0] == "TOKEN" and line[1]:
                TOKEN = line[1]
            if REPOSITORY is None and line[0] == "REPOSITORY" and line[1]:
                REPOSITORY = line[1]
            if COMMIT_SHA is None and line[0] == "COMMIT_SHA" and line[1]:
                COMMIT_SHA = line[1]
if TOKEN is None:
    raise Exception("No token could be found")
if REPOSITORY is None:
    raise Exception("No repository could be found")


def predict_and_suggest():
    print("Initializing")
    adaptor = GithubAdapter(TOKEN, REPOSITORY, COMMIT_SHA)
    detector = Detector(TOKEN, REPOSITORY, COMMIT_SHA)
    estimator = Estimator()

    print(f"Getting features, {datetime.now()}")
    features = adaptor.get_features()
    # flush_debug_csv(features)
    print(f"Getting defects, {datetime.now()}")
    defects = detector.mark_fix_and_get_defects(features)
    if len(features) < 20:
        print(f"The commit count must at least be 20, found {len(features)}")
        print(f"Finished, {datetime.now()}")
        exit(0)
    print(f"Estimating defect probability, {datetime.now()}")
    estimator.estimate(features, defects)
    print(f"Getting improvement suggestions, {datetime.now()}")
    estimator.suggest_improvement()
    print(f"Finished, {datetime.now()}")


def flush_debug_csv(features):
    csv_file_name = "debug.csv"
    with open(csv_file_name, "w", newline='', encoding="utf-8") as csv_file:
        csv_writer = csv.writer(csv_file)
        for commit in features.values():
            csv_writer.writerow(commit.to_list())


if __name__ == '__main__':
    predict_and_suggest()
