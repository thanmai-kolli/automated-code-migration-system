class UpgradeReport:

    def __init__(self):
        self.language = None
        self.detected_version = None
        self.target_version = None
        self.changes = []
        self.compile_success = None
        self.compile_errors = None
        self.risk_score = None
        self.risk_level = None
        self.validation_status = None

    def generate(self):
        return {
            "language": self.language,
            "detected_version": self.detected_version,
            "target_version": self.target_version,
            "changes": self.changes,
            "compile_success": self.compile_success,
            "compile_errors": self.compile_errors,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "validation_status": self.validation_status
        }
