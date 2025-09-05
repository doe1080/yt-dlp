import functools
import json
import uuid

from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    OnDemandPagedList,
    clean_html,
    extract_attributes,
    filter_dict,
    float_or_none,
    int_or_none,
    join_nonempty,
    parse_iso8601,
    parse_qs,
    unified_strdate,
    update_url,
    url_or_none,
    urljoin,
)
from ..utils.traversal import (
    find_element,
    find_elements,
    require,
    traverse_obj,
    trim_str,
)


class CeskaTelevizeBaseIE(InfoExtractor):
    _API_BASE = 'https://api.ceskatelevize.cz'
    _BASE_URL = 'https://www.ceskatelevize.cz'
    _GEO_BYPASS = False
    _GEO_COUNTRIES = ['CZ']


class CeskaTelevizeIE(CeskaTelevizeBaseIE):
    IE_NAME = 'ivysilani'
    IE_DESC = 'IVysílání'

    _VALID_URL = r'https?://(?:www\.)?ceskatelevize\.cz/porady/(?P<series_id>[^/?#]+)(?:/[^/?#]+)*/(?!bonus(?:[/?#]|$))(?P<id>[^/?#]+)'
    _TESTS = [{
        'url': 'https://www.ceskatelevize.cz/porady/13653549578-protivny-sprosty-matky/220562280020001/',
        'info_dict': {
            'id': '220562280020001',
            'ext': 'mp4',
            'title': 'Matky versus porod',
            'artists': 'count:1',
            'categories': 'count:4',
            'description': 'md5:59e3216adb75404ebcf3d95341804b84',
            'duration': 1207,
            'episode': 'Matky versus porod | 1',
            'episode_id': '648874d414116dd1ab0cc572',
            'media_type': 'video',
            'modified_date': '20250626',
            'modified_timestamp': 1750950226,
            'series': 'Protivný sprostý matky',
            'series_id': '13653549578-protivny-sprosty-matky',
            'thumbnail': r're:https?://(?:ctfs|img)\.ceskatelevize\.cz/.+',
            'timestamp': 1642633260,
            'upload_date': '20220119',
        },
        'params': {'skip_download': 'dash'},
    }, {
        # Geo-restricted to Czech Republic
        'url': 'https://www.ceskatelevize.cz/porady/16614972629-arkadie/225388770680001/',
        'info_dict': {
            'id': '225388770680001',
            'ext': 'mp4',
            'title': '1/8 Podvod',
            'alt_title': 'Arcadia S01 | De fraude',
            'artists': 'count:1',
            'categories': 'count:4',
            'description': 'md5:103b362536cbd4d52d2e1189f2821642',
            'duration': 2815.84,
            'episode': 'Podvod | 1',
            'episode_id': '66b24fb994a26ec9ef0ccfd1',
            'media_type': 'video',
            'modified_date': '20250806',
            'modified_timestamp': 1754517601,
            'season': 'I. řada',
            'season_id': '687e22a394d4d5d2280b4f03',
            'series': 'Arkádie',
            'series_id': '16614972629-arkadie',
            'thumbnail': r're:https?://(?:ctfs|img)\.ceskatelevize\.cz/.+',
            'timestamp': 1754517600,
            'upload_date': '20250806',
        },
        'params': {'skip_download': 'dash'},
    }, {
        # NFSW
        'url': 'https://www.ceskatelevize.cz/porady/10520528904-queer/222562210900005/',
        'info_dict': {
            'id': '222562210900005',
            'ext': 'mp4',
            'title': 'Cesty z nesvobody',
            'age_limit': 18,
            'artists': 'count:1',
            'categories': 'count:4',
            'description': 'md5:6a274ac369d9d2c1537cec068f9c1f7b',
            'duration': 1569,
            'episode': 'Cesty z nesvobody | 5',
            'episode_id': '6489776ec8d6106fa308cd9f',
            'media_type': 'video',
            'modified_date': '20250628',
            'modified_timestamp': 1751114400,
            'series': 'Queer',
            'series_id': '10520528904-queer',
            'thumbnail': r're:https?://(?:ctfs|img)\.ceskatelevize\.cz/.+',
            'timestamp': 1649973789,
            'upload_date': '20220414',
        },
        'params': {'skip_download': 'dash'},
    }, {
        # Bonus
        'url': 'https://www.ceskatelevize.cz/porady/898320-navstevnici/bonus/33182/',
        'info_dict': {
            'id': '33182',
            'ext': 'mp4',
            'title': '35 let od premiéry sci-fi seriálu Návštěvníci',
            'artists': 'count:1',
            'categories': 'count:8',
            'description': 'md5:c9afb056998e52929bf0662bc0e87fa9',
            'duration': 659,
            'episode': 'Studio 6 | 1105',
            'episode_id': '6488f804702e0abdf90c32ef',
            'media_type': 'video',
            'modified_date': '20250627',
            'modified_timestamp': 1751035495,
            'series': 'Návštěvníci',
            'series_id': '898320-navstevnici',
            'thumbnail': r're:https?://(?:ctfs|img)\.ceskatelevize\.cz/.+',
            'timestamp': 436834800,
            'upload_date': '19831104',
        },
        'params': {'skip_download': 'dash'},
    }, {
        # Bonus
        'url': 'https://www.ceskatelevize.cz/porady/10214135017-zazraky-prirody/11612-videa-z-poradu/43501-ohnostroj/',
        'info_dict': {
            'id': '43501',
            'ext': 'mp4',
            'title': 'Ohňostroj',
            'display_id': '43501-ohnostroj',
            'duration': 711,
            'media_type': 'video',
            'modified_date': '20250624',
            'modified_timestamp': 1750772160,
            'series': 'Zázraky přírody',
            'series_id': '10214135017-zazraky-prirody',
            'thumbnail': r're:https?://(?:ctfs|img)\.ceskatelevize\.cz/.+',
            'upload_date': '20230214',
        },
        'params': {'skip_download': 'dash'},
    }, {
        # Video gallery
        'url': 'https://www.ceskatelevize.cz/porady/10214135017-zazraky-prirody/11612-videa-z-poradu/fyzika/',
        'info_dict': {
            'id': 'fyzika',
            'title': 'Zázraky přírody',
        },
        'playlist_count': 47,
    }, {
        # VTT/TTML subtitles via API
        'url': ' https://www.ceskatelevize.cz/porady/1097181328-udalosti/217411000100214/',
        'only_matching': True,
    }, {
        # FIXME: Missing support for MPD segment based subtitles
        # WVTT/STPP subtitles in DASH manifest
        'url': ' https://www.ceskatelevize.cz/porady/1097181328-udalosti/225411000100830/',
        'only_matching': True,
    }, {
        # Not licensed for online streaming
        'url': ' https://www.ceskatelevize.cz/porady/133885-hadrian-z-rimsu/28031043757/',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        series_id, display_id = self._match_valid_url(url).group('series_id', 'id')
        video_id = display_id.partition('-')[0]
        webpage = self._download_webpage(url, display_id)
        nextjs_data = self._search_nextjs_data(webpage, display_id, fatal=False, default={})

        metadata = traverse_obj(nextjs_data, (
            'props', 'pageProps', 'data', ('mediaMeta', None), {dict}, any))
        if traverse_obj(metadata, ((None, 'show'), 'isPlayable', {bool}, any)) is False:
            msg = traverse_obj(metadata, ((None, 'show'), 'playabilityError', {clean_html}, filter, any))
            raise ExtractorError(
                msg or 'API returned an error response', expected=bool(msg))

        season_id = traverse_obj(metadata, ('activeSeasonId', {str}))
        series = traverse_obj(webpage, (
            {find_element(cls='header-row')}, {find_element(tag='h1')}, {clean_html}, filter))

        path = f'media/external/{video_id}'
        if '/bonus/' in url:
            path = f'bonus/BO-{video_id}'
        elif data_url := traverse_obj(webpage, (
            {find_element(cls='media-ivysilani-placeholder', html=True)},
            {extract_attributes}, 'data-url', {self._proto_relative_url}, {url_or_none},
        )):
            query = filter_dict({
                k.lower(): v[-1].strip() for k, v in parse_qs(data_url).items()}, lambda _, v: v)
            if (
                {'bonus', 'bonusid'} & query.keys()
                and {'index', 'indexid', 'mediaid', 'versionid', 'encoder', 'live', 'pfvideoaccess'}.isdisjoint(query)
            ):
                path = f'bonus/BO-{video_id}'
        elif gallery := traverse_obj(webpage, (
            {find_element(cls='gallery video-gallery', html=True)},
        )):
            return self.playlist_from_matches(traverse_obj(gallery, (
                {find_elements(cls='obsah', html=True)}, ...,
                {find_element(tag='a', html=True)}, {extract_attributes},
                'href', {str}, filter, {urljoin(self._BASE_URL)},
            )), display_id, series, ie=CeskaTelevizeIE)

        stream_data = self._download_json(
            f'{self._API_BASE}/video/v1/playlist-vod/v1/stream-data/{path}',
            video_id, query={
                'canPlayDrm': 'true',
                'quality': 'web',
                'streamType': 'dash',
                'sessionId': str(uuid.uuid4()),
                'origin': 'ivysilani',
                'usePlayability': 'true',
                'client': 'ivysilaniweb',
            }, expected_status=403)

        if message := traverse_obj(stream_data, ('message', {dict})):
            status = traverse_obj(message, ('status', 'name', {str}, filter))
            msg = traverse_obj(message, ('labels', 'textLong', {clean_html}, filter))
            if (
                status == 'UNSUPPORTED_GEOLOCATION'
                or traverse_obj(message, ('labels', 'generalError', {str})) == 'GEO'
            ):
                self.raise_geo_restricted(
                    msg, countries=self._GEO_COUNTRIES, metadata_available=True)
            else:
                raise ExtractorError(
                    join_nonempty(status, msg, delim=': '), expected=True)

        chapters = traverse_obj(stream_data, ('streams', ..., 'chapters', lambda _, v: v['time'], {
            'start_time': ('time', {int_or_none}),
            'title': ('title', {clean_html}),
        })) or None

        formats, subtitles = [], {}
        for stream_url in traverse_obj(stream_data, (
            'streams', ..., ('url', 'audioDescriptionUrl'), {url_or_none},
        )):
            urlh = self._request_webpage(stream_url, video_id)
            fmts, _ = self._extract_mpd_formats_and_subtitles(urlh.url, video_id, fatal=False)
            formats.extend(fmts)

        for subs in traverse_obj(stream_data, ('streams', ..., 'subtitles', ...)):
            lang = subs.get('locale', 'ces')
            for sub in traverse_obj(subs, (
                'files', lambda _, v: url_or_none(v['url']),
            )):
                subtitles.setdefault(lang, []).append({
                    'ext': sub.get('format'),
                    'url': sub['url'],
                })

        return {
            'id': video_id,
            'title': traverse_obj(webpage, (
                {find_element(cls='video_bonus-title', html=True)}, {clean_html}, filter)),
            'chapters': chapters,
            'display_id': display_id,
            'formats': formats,
            'series': series,
            'series_id': series_id,
            'subtitles': subtitles,
            'thumbnail': self._og_search_thumbnail(webpage),
            'upload_date': unified_strdate(self._html_search_meta(
                'uploadDate', webpage, 'upload date', default=None)),
            **self._search_json_ld(webpage, video_id, fatal=False, default={}),
            **traverse_obj(stream_data, {
                'age_limit': ('pegiRating', {int_or_none}),
                'alt_title': ('originalTitle', {clean_html}, filter),
                'duration': ('duration', {float_or_none}),
                'episode': ('episodeTitle', {clean_html}, filter),
                'media_type': ('mediaType', {str}),
            }),
            **traverse_obj(stream_data, ('playability', {
                'episode_id': ('episodeProgrammeMetaId', {str}),
                'modified_timestamp': ('updatedAt', {parse_iso8601}),
            })),
            **traverse_obj(metadata, ('show', {
                'categories': ('flatGenres', ..., 'title', {clean_html}, filter, all, filter),
                'series': ('title', {clean_html}, filter),
            })),
            **traverse_obj(metadata, (
                'show', 'seasons', lambda _, v: v.get('id') == season_id, any, {
                    'season': ('title', {clean_html}, filter),
                    'season_id': ('id', {str}, {trim_str(start='season:')}, filter),
                },
            )),
        }


class CeskaTelevizeSeriesIE(CeskaTelevizeBaseIE):
    IE_NAME = 'ivysilani:series'

    _PAGE_SIZE = 40
    _VALID_URL = r'https?://(?:www\.)?ceskatelevize\.cz/porady/(?P<id>[\w-]+)(?:/bonus)?/?(?:[?#]|$)'
    _TESTS = [{
        'url': 'https://www.ceskatelevize.cz/porady/10614999031-neviditelni/',
        'info_dict': {
            'id': '10614999031-neviditelni',
            'title': 'Neviditelní',
            'description': 'md5:2a462332ab653ca9be0a0d2444463264',
        },
        'playlist_count': 13,
    }, {
        # Seasons
        'url': 'https://www.ceskatelevize.cz/porady/10111864738-hercule-poirot/',
        'info_dict': {
            'id': '10111864738-hercule-poirot',
            'title': 'Hercule Poirot',
            'description': 'md5:c3d2679ee5ec10b17f872abbf4bec9ca',
        },
        'playlist_count': 71,
    }, {
        # Bonus
        'url': 'https://www.ceskatelevize.cz/porady/898320-navstevnici/bonus/',
        'info_dict': {
            'id': '898320-navstevnici',
            'title': 'Videobonusy',
        },
        'playlist_count': 5,
    }]

    def _fetch_page(self, series_id, idec, page):
        graphql = self._download_json(
            f'{self._API_BASE}/graphql/', series_id,
            f'Downloading page {page + 1}', query={
                'client': 'iVysilaniWeb',
                'version': '1.159.0',
                'operationName': 'GetEpisodes',
                'variables': json.dumps({
                    'idec': idec,
                    'limit': self._PAGE_SIZE,
                    'offset': page * self._PAGE_SIZE,
                    'onlyPlayable': False,
                    'orderBy': 'oldest',
                }, separators=(',', ':')),
                'extensions': json.dumps({
                    'persistedQuery': {
                        'version': 1,
                        'sha256Hash': 'daadc108145dc4ea3466b4ee224a8cfbfd42d3486dbc13f1a1b6e064ffc8f692',
                    },
                }, separators=(',', ':')),
            })

        for item in traverse_obj(graphql, (
            'data', 'episodesPreviewFind', 'items', ..., {dict},
        )):
            show_id, show_code, video_id = traverse_obj(item, (('showId', 'showCode', 'id'), {str}))

            yield self.url_result(
                f'{self._BASE_URL}/porady/{show_id}-{show_code}/{video_id}/', CeskaTelevizeIE)

    def _real_extract(self, url):
        series_id = self._match_id(url)
        webpage = self._download_webpage(url, series_id)
        show = self._search_nextjs_data(webpage, series_id)['props']['pageProps']['data']['show']
        idec = traverse_obj(show, ('idec', {str}, {require('idec')}))

        if '/bonus' in url:
            return self.playlist_from_matches(traverse_obj(show, (
                'videobonuses', ..., 'bonusId', {str},
                filter, {urljoin(update_url(url, query=None))},
            )), series_id, 'Videobonusy', ie=CeskaTelevizeIE)

        return self.playlist_result(OnDemandPagedList(
            functools.partial(self._fetch_page, series_id, idec), self._PAGE_SIZE),
            series_id, **traverse_obj(show, {
                'title': ('title', {clean_html}, filter),
                'description': ('shortDescription', {clean_html}, filter),
            }))
