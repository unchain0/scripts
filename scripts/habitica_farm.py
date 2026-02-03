import os
import time
from dataclasses import dataclass

import requests
from dotenv import load_dotenv
from loguru import logger

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Configuration for the Habitica Farmer."""

    user_id: str
    api_key: str
    task_id: str
    client_id: str
    base_url: str = "https://habitica.com/api/v3"
    delay_seconds: float = 1.0
    error_delay_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        user_id = os.getenv("HABITICA_USER_ID")
        api_key = os.getenv("HABITICA_API_KEY")
        task_id = os.getenv("HABITICA_TASK_ID")

        if not all([user_id, api_key, task_id]):
            raise ValueError(
                "Missing required environment variables. "
                "Please ensure HABITICA_USER_ID, HABITICA_API_KEY, and HABITICA_TASK_ID are set."
            )

        return cls(
            user_id=user_id,  # type: ignore[bad-argument-type]
            api_key=api_key,  # type: ignore[bad-argument-type]
            task_id=task_id,  # type: ignore[bad-argument-type]
            client_id=os.getenv("HABITICA_CLIENT", f"{user_id}-Testing"),
        )


class HabiticaFarmer:
    """Handles the interaction with the Habitica API to farm tasks."""

    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self._configure_session()
        self.url = f"{self.config.base_url}/tasks/{self.config.task_id}/score/up"
        self._counter = 0

    def _configure_session(self) -> None:
        """Set up the session headers."""
        self.session.headers.update(
            {
                "x-api-user": self.config.user_id,
                "x-api-key": self.config.api_key,
                "x-client": self.config.client_id,
                "Content-Type": "application/json",
            }
        )

    def run(self) -> None:
        """Start the main farming loop."""
        logger.info(f"Starting farming for task ID: {self.config.task_id}")
        logger.info("Press Ctrl+C to stop.")

        try:
            self._farm_loop()
        except KeyboardInterrupt:
            logger.info("\nStopping script...")

    def _farm_loop(self) -> None:
        """The infinite loop that performs the task scoring."""
        while True:
            self._counter += 1
            self._perform_single_cast()

    def _perform_single_cast(self) -> None:
        """Performs a single API request and handles the response/sleeping."""
        try:
            response = self.session.post(self.url, timeout=10)
            self._handle_response(response)
        except requests.RequestException as e:
            logger.error(f"Iteration {self._counter}: Connection/Request error: {e}")
            self._sleep(self.config.error_delay_seconds)
        except ValueError as e:
            logger.exception(f"Iteration {self._counter}: Unexpected error: {e}")
            self._sleep(self.config.error_delay_seconds)

    def _handle_response(self, response: requests.Response) -> None:
        """Process the API response.

        Args:
            response (requests.Response): The API response.
        """
        if response.ok:
            logger.success(f"Iteration {self._counter}: {response.status_code} - OK")
            self._sleep(self.config.delay_seconds)
            return

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait_time = (
                int(retry_after) if retry_after else self.config.error_delay_seconds
            )
            logger.warning(
                f"Iteration {self._counter}: Rate limited (429). Retrying in {wait_time}s."
            )
            self._sleep(wait_time)
        else:
            logger.warning(
                f"Iteration {self._counter}: Failed with status {response.status_code}"
            )
            logger.warning(f"Response: {response.text}")
            self._sleep(self.config.error_delay_seconds)

    def _sleep(self, seconds: float) -> None:
        """Sleep wrapper for cleaner code.

        Args:
            seconds (float): The number of seconds to sleep.
        """
        time.sleep(seconds)


def main() -> None:
    try:
        config = Config.from_env()
        farmer = HabiticaFarmer(config)
        farmer.run()
    except ValueError as e:
        logger.error(str(e))
    except Exception as e:
        logger.exception(f"Fatal error: {e}")


if __name__ == "__main__":
    main()
