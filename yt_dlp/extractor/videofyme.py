from .common import InfoExtractor
from ..utils import clean_html, int_or_none
from ..utils.traversal import (
    find_element,
    traverse_obj,
    trim_str,
)


class VideofyMeIE(InfoExtractor):
    IE_NAME = 'videofy.me'
    IE_DESC = 'Videofy.me'

    _VALID_URL = r'https?://(?:(?:p|www)\.)?videofy\.me/v/(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://www.videofy.me/v/882107',
        'info_dict': {
            'id': '882107',
            'ext': 'mp4',
            'title': 'This is VideofyMe',
            'comment_count': int,
            'description': '',
            'thumbnail': r're:https?://videothumb\.videofy\.me/.+\.jpg',
            'timestamp': 1364281642,
            'upload_date': '20130326',
            'uploader_id': 'thisisvideofyme',
            'view_count': int,
        },
    }, {
        'url': 'https://p.videofy.me/v/315598',
        'info_dict': {
            'id': '315598',
            'ext': 'mp4',
            'title': 'så bra den vart',
            'comment_count': int,
            'description': 'md5:14f0e1345e078347ddbaa5bca4608ad8',
            'thumbnail': r're:https?://videothumb\.videofy\.me/.+\.jpg',
            'timestamp': 1326781151,
            'upload_date': '20120117',
            'uploader_id': 'g4pvuwf4',
            'view_count': int,
        },
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)

        return {
            'id': video_id,
            'comment_count': int_or_none(self._search_regex(
                r'(\d+)\s+Comments', webpage, 'comment count', default=0)),
            **self._search_json_ld(webpage, video_id),
            **traverse_obj(webpage, {
                'like_count': ({find_element(cls='sl-count')}, {int_or_none}),
                'uploader_id': (
                    {find_element(cls='betube_mag__heading_head betube_mag__heading_author')},
                    {clean_html}, {trim_str(start='By :')}, {str.strip},
                ),
            }),
        }
