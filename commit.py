class Commit:

    def __init__(self):
        """ A simple feature container for each git commit """
        self.features = {}

    def add(self, key, value):
        if key in self.features:
            raise Exception("Do not overwrite features")
        self.features[key] = value

    def remove(self, key):
        if key in self.features:
            return self.features.pop(key)
        raise Exception(f"The commit object does not have the feature: {key}")

    def get(self, key):
        if key in self.features:
            return self.features[key]
        raise Exception(f"The commit object does not have the feature: {key}")

    def get_all(self):
        return self.features.copy()

    def to_list(self):
        tmp = self.features.copy()
        tmp.pop("message", None)
        tmp.pop("files", None)
        return list(tmp.values())
