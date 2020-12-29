from datetime import datetime

import time
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message


class TooManyRequestsRetryMiddleware(RetryMiddleware):
    def __init__(self, crawler):
        super(TooManyRequestsRetryMiddleware, self).__init__(crawler.settings)
        self.crawler = crawler
        self.last429Error = datetime.strptime('2000-01-01T00:00:00.000', "%Y-%m-%dT%H:%M:%S.%f")

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def process_response(self, request, response, spider):
        if request.meta.get('dont_retry', False):
            return response

        if response.status == 429:  # Too many requests
            secondsSinceLast429Error = (datetime.now() - self.last429Error).total_seconds()

            self.crawler.engine.pause()

            if secondsSinceLast429Error > 70:
                print("429 occurred. Waiting for 60 seconds before continuing.")
                time.sleep(60)  # Sleep 60 seconds.
            else:
                print("429 occurred. Waiting for 60 minutes before continuing.")
                time.sleep(60 * 60)  # Sleep 1 hour.

            self.crawler.engine.unpause()
            self.last429Error = datetime.now()

        if response.status in self.retry_http_codes:
            reason = response_status_message(response.status)
            return self._retry(request, reason, spider) or response

        return response
