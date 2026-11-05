class DomainError(Exception):
    def __init__(self, code: str, status: int = 409, detail: str | None = None):
        self.code = code
        self.status = status
        # Internal explanation (e.g. the payment provider's message); never sent to clients.
        self.detail = detail
        super().__init__(code)
