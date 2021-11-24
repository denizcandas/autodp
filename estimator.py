import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

CI_STATES = ["failure", "pending", "success"]


class Estimator:

    def __init__(self):
        self.clf = None
        self.feature_labels = None
        self.target_feature = None
        self.original_defect_probability = None

    def estimate(self, commits, defects):
        clf = RandomForestClassifier(max_features='log2', max_samples=0.3, random_state=42)
        features = []
        self.feature_labels = None
        feature_labels = []
        for commit in commits.values():
            instance = []
            for col in commit.get_all():
                if col in ["sha", "index", "files", "message"]:
                    continue
                if self.feature_labels is None:
                    feature_labels.append(col)
                value = commit.get(col)
                if type(value) in [int, float]:
                    instance.append(np.log10(value + 1))
                elif type(value) == bool:
                    instance.append(value)
                elif col == "ci_state":
                    if value in CI_STATES:
                        instance.append(CI_STATES.index(value))
                    else:
                        raise Exception(f"Unknown CI state: {value}")
                else:
                    sha = commit.get("sha")
                    raise Exception(f"Column {col} with value {value} could not be parsed for commit {sha}")
            features.append(instance)
            if self.feature_labels is None:
                self.feature_labels = feature_labels
            if len(instance) != len(self.feature_labels):
                raise Exception("Machine learning instance does not have the correct count of labels")
        target_size = int(len(features) * 0.8)
        train_features, train_labels = features[:target_size], defects[:target_size]
        test_features, test_labels = features[target_size:], defects[target_size:]
        clf.fit(train_features, train_labels)
        predictions = clf.predict(test_features)
        prediction_count = (predictions == 1).sum()
        print(f"Of {len(predictions)} predictions, predicted {prediction_count} defects,"
              f"and actual defect count was {test_labels.count(True)}\n"
              f"Accuracy: {accuracy_score(test_labels, predictions):.2%} "
              f"Precision: {precision_score(test_labels, predictions):.2%} "
              f"Recall: {recall_score(test_labels, predictions):.2%} "
              f"F1: {f1_score(test_labels, predictions):.2%} ")
        clf.fit(features[:-1], defects[:-1])
        self.clf = clf
        self.target_feature = features[-1]
        self.original_defect_probability = clf.predict_proba([features[-1]])[0][1]
        print(f"The probability of a defect is {self.original_defect_probability:.2%}")
        if defects[-1] and features[self.feature_labels.index("ci_state")] == "failure":
            print(f"The commit is probably a defect due to a failing CI")

    def suggest_improvement(self):
        suggestions = []
        suggestion_text = None
        for i in range(len(self.target_feature)):
            feature_copy = self.target_feature.copy()
            if type(feature_copy[i]) in [int, float]:
                feature_copy[i] -= np.log10(2)  # divide the value in 2: log10(x/2) = log10(x) - log10(2)
                suggestion_text = f"Create half as many changes for {self.feature_labels[i]}"
            if type(feature_copy[i]) == bool:
                feature_copy[i] = not feature_copy[i]
                suggestion_text = f"Ensure that {self.feature_labels[i]} is {feature_copy[i]}"
            if self.feature_labels[i] == "ci_state":
                feature_copy[i] = CI_STATES.index("success")
                suggestion_text = f"Ensure that the CI results are successful"
            probability = self.clf.predict_proba([feature_copy])[0][1]
            suggestions.append((suggestion_text, probability))
        suggestions.sort(key=(lambda x: x[1]))
        is_better_suggestion = False
        for suggestion_text, probability in suggestions:
            if probability < self.original_defect_probability:
                is_better_suggestion = True
                print(f"{suggestion_text}, which lowers defect probability to {probability:.2%}")
        if not is_better_suggestion:
            print("There is no suggestion for an improvement")
