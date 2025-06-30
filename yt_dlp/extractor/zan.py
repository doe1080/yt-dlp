from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    clean_html,
    extract_attributes,
    parse_iso8601,
    parse_resolution,
    urlencode_postdata,
    urljoin,
)
from ..utils.traversal import find_element, traverse_obj


class ZanIE(InfoExtractor):
    IE_NAME = 'zan'
    IE_DESC = 'Z-aN'

    _BASE_URL = 'https://www.zan-live.com'
    _VALID_URL = r'https?://(www\.)?zan-live\.com/[^/]+/live/play/\d+/(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://www.zan-live.com/en/live/play/1797/663',
        'info_dict': {
            'id': '663',
            'ext': 'mp4',
            'title': 'The sample video page',
            'description': 'md5:12ba331396215fe345b9362c56f3da86',
            'release_date': '20220228',
            'release_timestamp': 1646060400,
            'thumbnail': r're:https?://storage\.zan-live\.com/image/.+\.(?:jpe?g|png)',
        },
    }, {
        'url': 'https://www.zan-live.com/ja/live/play/4137/2640',
        'info_dict': {
            'id': '2640',
            'ext': 'mp4',
            'title': '「マッシュル-MASHLE-」THE STAGE',
            'description': 'md5:41d5108579b20b851a86a5d11fe8fdaa',
            'release_date': '20240830',
            'release_timestamp': 1724986800,
            'thumbnail': r're:https?://storage\.zan-live\.com/image/.+\.(?:jpe?g|png)',
        },
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        csrf_token = self._html_search_meta('csrf-token', webpage, default=None)
        pct = self._html_search_meta('vod-pct', webpage, default=None)
        token = self._html_search_meta('live-player-token', webpage, default=None)
        if not all((csrf_token, pct, token)):
            self.raise_login_required()

        status = self._download_json(
            f'{self._BASE_URL}/api/live/{video_id}/getLiveStatus', video_id, headers={
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Csrf-Token': csrf_token,
            }, data=urlencode_postdata({
                'pct': pct,
                'token': token,
            }))
        if not traverse_obj(status, ('isSuccess', {bool})):
            self.raise_login_required()

        result = status['result']
        if not traverse_obj(result, ('isVod', {bool})):
            raise ExtractorError('Video is not yet archived', expected=True)
        elif traverse_obj(result, ('isFinished', {bool})):
            raise ExtractorError('Video Expired', expected=True)
        elif not traverse_obj(result, ('canPlay', {bool})):
            raise ExtractorError('Ticket Expired', expected=True)

        m3u8_url = self._html_search_meta('live-url', webpage, fatal=True)
        formats = self._extract_m3u8_formats(m3u8_url, video_id, 'mp4')
        for fmt in formats:
            fmt.update(parse_resolution(fmt['url'].split('/')[-2]))

        detail_url = traverse_obj(webpage, (
            {find_element(cls='linkTxt')},
            {find_element(cls='d-flex align-items-center', html=True)},
            {extract_attributes}, 'href', {urljoin(self._BASE_URL)}))
        detail = self._download_webpage(detail_url, video_id)

        return {
            'id': video_id,
            'title': clean_html(self._og_search_title(detail)),
            'description': traverse_obj(detail, ({find_element(cls='groupDetail')}, {clean_html})),
            'formats': formats,
            'release_timestamp': parse_iso8601(self._html_search_meta('open-live-date', webpage)),
            'thumbnail': self._og_search_thumbnail(detail),
        }
