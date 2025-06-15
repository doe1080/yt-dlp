from .rambler import RamblerBaseIE
from ..utils import (
    ExtractorError,
    clean_html,
    extract_attributes,
    parse_iso8601,
)
from ..utils.traversal import (
    find_element,
    find_elements,
    traverse_obj,
    trim_str,
)


class GazetaIE(RamblerBaseIE):
    IE_NAME = 'gazeta'
    IE_DESC = 'Газета.ru'

    _VALID_URL = r'https?://(?:www\.)?gazeta\.ru/(?:[a-z]+/)+(?:\d{4}/\d{2}/\d{2}/)?(?P<id>\d{8})(?:/[\w-]+)?\.shtml'
    _TESTS = [{
        'url': 'https://www.gazeta.ru/social/news/2025/06/12/26023262.shtml',
        'info_dict': {
            'id': 'record::37ab2f3c-cc2f-4137-bb2a-8cbbc2a18fb0',
            'ext': 'mp4',
            'title': 'Самое высокое здание мира подсветили в цвета российского флага',
            'alt_title': 'Небоскреб Бурдж-Халифа подсветили в цвета флага РФ',
            'description': 'md5:105373c911f35c452f83e49084066f5f',
            'display_id': '26023262',
            'release_date': '20250612',
            'release_timestamp': 1749756526,
            'thumbnail': r're:https?://.+\.(?:jpe?g|png)',
            'uploader': 'Иван Лесюк',
            'uploader_id': 'ivan_lesyuk',
        },
    }, {
        'url': 'https://www.gazeta.ru/science/2025/05/11/20913404.shtml',
        'info_dict': {
            'id': 'record::c31d1a80-9fe9-416b-8cf6-30d0f645534f',
            'ext': 'mp4',
            'title': 'Застрявшие на льдине. Как прошла российско-бразильская кругосветка по изучению Антарктиды',
            'alt_title': 'Полярник Куссе-Тюз: начинаются непредсказуемые изменения в экосистемах Антарктиды',
            'categories': ['Наука'],
            'description': 'md5:92abdfca372dea985e8e23c40976027a',
            'display_id': '20913404',
            'release_date': '20250511',
            'release_timestamp': 1746939625,
            'thumbnail': r're:https?://.+\.(?:jpe?g|png)',
            'uploader': 'Валерия Бунина',
            'uploader_id': 'valeriya_bunina',
        },
    }, {
        'url': 'https://www.gazeta.ru/culture/20884826/pozdravleniya-s-paskhoj.shtml',
        'info_dict': {
            'id': 'record::f73d7b17-9c4a-4796-96a3-a4f9fabec15e',
            'ext': 'mp4',
            'title': 'Как поздравить с Пасхой в 2025 году и почему принято говорить «Христос воскресе!»',
            'alt_title': 'Как правильно говорить — «Христос воскресе!» или «Христос воскрес!»',
            'categories': ['Культура'],
            'description': 'md5:8e297ff022f9d67c22f2edcf293a3be1',
            'display_id': '20884826',
            'release_date': '20250417',
            'release_timestamp': 1744865990,
            'thumbnail': r're:https?://.+\.(?:jpe?g|png)',
            'uploader': 'Анна Гавришева',
            'uploader_id': 'anna_gavrisheva',
        },
    }, {
        'url': 'https://www.gazeta.ru/politics/2025/06/13/21203534.shtml',
        'info_dict': {
            'id': '21203534',
        },
        'playlist_count': 12,
    }]

    def _real_extract(self, url):
        display_id = self._match_id(url)
        webpage = self._download_webpage(url, display_id)

        rambler_ids = traverse_obj(webpage, (
            {find_elements(tag='div', attr='data-widget', value='Player', html=True)},
            ..., {extract_attributes}, 'data-id', {str}, filter, all, filter))
        if not rambler_ids:
            raise ExtractorError('No video found', expected=True)

        entries = [{
            **self._extract_from_rambler_api(rambler_id, url),
            'display_id': display_id,
            **traverse_obj(webpage, {
                'title': ({find_element(cls='headline')}, {clean_html}),
                'alt_title': ({find_element(cls='subheader')}, {clean_html}),
                'categories': ({find_element(cls='rubric')}, {clean_html}, filter, all, filter),
                'description': ({find_element(cls='b_article-text')}, {clean_html}),
                'release_timestamp': (
                    {find_element(tag='time', attr='itemprop', value='datePublished', html=True)},
                    {extract_attributes}, 'datetime', {parse_iso8601},
                ),
            }),
            **traverse_obj(webpage, ({find_element(cls='author-item', html=True)}, {
                'uploader': {clean_html},
                'uploader_id': ({extract_attributes}, 'itemid', {trim_str(start='/gazeta/authors/', end='.shtml')}, {str}),
            })),
        } for rambler_id in rambler_ids]

        if len(entries) == 1:
            return entries[0]
        return self.playlist_result(entries, display_id)
