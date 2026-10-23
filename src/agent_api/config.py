from dataclasses import dataclass
import os
import re


@dataclass(frozen=True)
class Settings:
    database_url: str
    api_key: str
    allowed_customer_ids: tuple[str, ...] = ('cus_001',)
    rate_limit: int = 60
    rate_window_seconds: float = 60.0

    def __post_init__(self):
        if not self.database_url or len(self.api_key) < 24 or not self.api_key.isascii():
            raise ValueError('DATABASE_URL and an ASCII API_KEY of at least 24 characters are required')
        if not self.allowed_customer_ids or any(not re.fullmatch(r'cus_[0-9]{3}', x) for x in self.allowed_customer_ids):
            raise ValueError('Allowed customer IDs must match cus_001 format')
        if self.rate_limit < 1 or not 0 < self.rate_window_seconds <= 3600:
            raise ValueError('Rate limit and window must be positive and window <=3600 seconds')

    @classmethod
    def from_env(cls):
        return cls(database_url=os.environ.get('DATABASE_URL', ''), api_key=os.environ.get('API_KEY', ''),
                   allowed_customer_ids=tuple(x.strip() for x in os.getenv('ALLOWED_CUSTOMER_IDS', 'cus_001').split(',') if x.strip()),
                   rate_limit=int(os.getenv('RATE_LIMIT','60')),
                   rate_window_seconds=float(os.getenv('RATE_WINDOW_SECONDS','60')))
