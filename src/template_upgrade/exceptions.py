class UpgradeError(Exception):

class TemplateNotFoundError(UpgradeError):

class VersionDetectionError(UpgradeError):

class VersionPathError(UpgradeError):

class BackupError(UpgradeError):

class CacheDiskError(UpgradeError):

class AgentError(UpgradeError):

    def __init__(self, message: str, exit_code: int=-1, stderr_tail: str=''):
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr_tail = stderr_tail

class DiskSpaceError(AgentError):

    def __init__(self, needed_mb: int):
        super().__init__(f'Template root partition needs {needed_mb} MB more space.', exit_code=1)
        self.needed_mb = needed_mb

class VerificationError(UpgradeError):

    def __init__(self, expected: int, actual: int):
        super().__init__(f'Version mismatch after upgrade: expected {expected}, got {actual}.')
        self.expected = expected
        self.actual = actual

class RollbackError(UpgradeError):

class MaxRetriesExceeded(UpgradeError):
