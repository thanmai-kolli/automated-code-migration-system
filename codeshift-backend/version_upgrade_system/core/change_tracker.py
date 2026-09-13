class ChangeTracker:

    def __init__(self):
        self.changes = []

    def add(self, rule_name):
        self.changes.append(rule_name)

    def total(self):
        return len(self.changes)

    def get_all(self):
        return self.changes
