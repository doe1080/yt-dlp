import json

from .common import InfoExtractor
from ..utils import (
    clean_html,
    extract_attributes,
    float_or_none,
    int_or_none,
    str_or_none,
    url_or_none,
)
from ..utils.traversal import (
    find_element,
    require,
    traverse_obj,
)


class DondoraOnlineIE(InfoExtractor):
    _VALID_URL = r'https?://dondora\.online/\w+/lessons/(?P<id>[\w-]+)/\w+'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        dom_id = traverse_obj(webpage, (
            {find_element(tag='body', id='student')},
            {find_element(tag='div', html=True)},
            {extract_attributes}, 'id', {str}, filter, {require('DOM ID')}))

        video_data = traverse_obj(webpage, (
            {find_element(tag='script', attr='data-dom-id', value=dom_id)},
            {json.loads}, {dict}))
        m3u8_url = traverse_obj(video_data, (
            'video', 'url', {url_or_none}, {require('m3u8 URL')}))

        return {
            'id': video_id,
            'formats': self._extract_m3u8_formats(m3u8_url, video_id, 'mp4'),
            **traverse_obj(video_data, {
                'duration': ('video', 'durationMsec', {float_or_none(scale=1000)}),
                'uploader_id': ('schoolCode', {str}, filter),
            }),
            **traverse_obj(video_data, ('lessonAttributes', {
                'title': ('name', {clean_html}, filter),
                'episode': ('name', {clean_html}, filter),
                'episode_number': ('stage', {int_or_none}),
                'series': ('courseOrItem', {clean_html}, filter),
                'series_id': ('courseOrItemNumber', {int}, {str_or_none}),
            })),
        }
