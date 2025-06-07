import functools

from .common import InfoExtractor
from ..utils import str_or_none, url_or_none
from ..utils.traversal import traverse_obj


class AsobiStageIE(InfoExtractor):
    IE_NAME = 'asobistage'
    IE_DESC = 'ASOBI STAGE'

    _VALID_URL = r'https?://asobistage\.asobistore\.jp/event/(?P<id>(?P<event>\w+)/(?P<type>archive|player|premium_lp)/(?P<slug>\w+))(?:[?#]|$)'
    _TESTS = [{
        'url': 'https://asobistage.asobistore.jp/event/idolmaster_idolworld2023_goods/archive/live',
        'info_dict': {
            'id': 'idolmaster_idolworld2023_goods/archive/live',
            'title': 'md5:378510b6e830129d505885908bd6c576',
        },
        'playlist': [{
            'info_dict': {
                'id': '3aef7110',
                'ext': 'mp4',
                'title': 'asobistore_station_1020_serverREC',
                'thumbnail': r're:https?://[\w.-]+/\w+/\w+',
            },
        }],
        'playlist_count': 1,
    }, {
        'url': 'https://asobistage.asobistore.jp/event/315passionhour_2022summer/archive/frame',
        'info_dict': {
            'id': '315passionhour_2022summer/archive/frame',
            'title': '315プロダクションプレゼンツ 315パッションアワー!!!',
        },
        'playlist_count': 1,
        'skip': 'Premium members only',
    }, {
        'url': 'https://asobistage.asobistore.jp/event/sidem_fclive_bpct/archive/premium_hc',
        'info_dict': {
            'id': 'sidem_fclive_bpct/archive/premium_hc',
            'title': '315 Production presents F＠NTASTIC COMBINATION LIVE ～BRAINPOWER!!～/～CONNECTIME!!!!～',
        },
        'playlist_count': 4,
        'skip': 'Paid video',
    }, {
        'url': 'https://asobistage.asobistore.jp/event/gakuen_1stperiod/premium_lp/ss_premium',
        'info_dict': {
            'id': 'gakuen_1stperiod/premium_lp/ss_premium',
            'title': '学園アイドルマスター The 1st Period Spotlight Star/Harmony Star',
        },
        'playlist_count': 2,
        'skip': 'Paid video',
    }, {
        'url': 'https://asobistage.asobistore.jp/event/ijigenfes_utagassen/player/day1',
        'only_matching': True,
    }]

    _API_HOST = 'https://asobistage-api.asobistore.jp'
    _HEADERS = {}
    _is_logged_in = False
    _is_premium = False
    _need_auth = False

    @functools.cached_property
    def _owned_tickets(self):
        owned_tickets = set()
        if not self._is_logged_in:
            return owned_tickets

        for path, name in [
            ('api/v1/purchase_history/list', 'ticket purchase history'),
            ('api/v1/serialcode/list', 'redemption history'),
        ]:
            response = self._download_json(
                f'{self._API_HOST}/{path}', None, f'Downloading {name}',
                f'Unable to download {name}', expected_status=400)
            if traverse_obj(response, ('payload', 'error_message'), 'error') == 'notlogin':
                self._is_logged_in = False
                break
            owned_tickets.update(traverse_obj(response, (
                'payload', 'value', ..., ('digital_product_id', 'itemid'), {str_or_none}, filter)))

        return owned_tickets

    def _get_available_channel_id(self, channels, video_type):
        for channel in channels:
            if video_type == 'premium_lp':
                self._need_auth = True
                channel_ids = traverse_obj(channel, (
                    'contentList', ..., 'contents', ...,
                    'movieUrl', {lambda x: x.rpartition('/')[-1]}, filter))
                available_ids = traverse_obj(channel, (
                    'availableCheckList', ('digital_product_id', 'serial_code'),
                    ..., {str_or_none}, filter))
            else:
                channel_ids = traverse_obj(channel, ('chennel_vspf_id', {str}, filter, all))
                # rights_type_id 6: public; 3: needs_premium
                if traverse_obj(channel, (
                    'viewrights', lambda _, v: v['rights_type_id'] == 6
                    or (v['rights_type_id'] == 3 and self._is_premium),
                )):
                    yield from channel_ids
                else:
                    self._need_auth = True
                    available_ids = traverse_obj(channel, (
                        'viewrights', ..., ('tickets', 'serialcodes'), ...,
                        ('digital_product_id', 'serial_id'), {str_or_none}, filter))

            if self._need_auth:
                if self._owned_tickets.intersection(available_ids):
                    yield from channel_ids
                else:
                    self.report_warning(
                        f'You are not a ticketholder for "{traverse_obj(channel, (("channel_name", "title"), any))}"')

    def _real_initialize(self):
        login = self._download_json(
            f'{self._API_HOST}/api/v1/check_login', None,
            'Checking login', 'Unable to check login', expected_status=400)
        if login['result'] == 'success':
            self._is_logged_in = traverse_obj(login, ('payload', 'is_login', {bool}))
            self._is_premium = traverse_obj(login, ('payload', 'm_type', {str})) == '2'

        token = self._download_json(
            f'{self._API_HOST}/api/v1/vspf/token', None, 'Getting token', 'Unable to get token')
        self._HEADERS['Authorization'] = f'Bearer {token}'

    def _real_extract(self, url):
        webpage, urlh = self._download_webpage_handle(url, self._match_id(url))
        video_id, event, type_, slug = self._match_valid_url(urlh.url).group('id', 'event', 'type', 'slug')
        video_type, type_key = {
            'archive': ('archives', 'archives'),
            'player': ('broadcasts', 'broadcasts'),
            'premium_lp': ('premium_lp', 'contents'),
        }[type_]

        path = ('channels', lambda _, v: len(v['chennel_vspf_id']) == 8) if video_type != 'premium_lp' else ()
        channels = traverse_obj(self._download_json(
            f'https://asobistage.asobistore.jp/cdn/v101/events/{event}/{video_type}.json',
            video_id, 'Getting channel list', 'Unable to get channel list',
        ), (type_key, lambda _, v: slug in map(v.get, ('broadcast_slug', 'premium_lp_slug')), *path))

        entries = []
        for channel_id in self._get_available_channel_id(channels, video_type):
            if video_type in ('archives', 'premium_lp'):
                channel_json = self._download_json(
                    f'https://survapi.channel.or.jp/proxy/v1/contents/{channel_id}/get_by_cuid', channel_id,
                    'Getting archive channel info', 'Unable to get archive channel info', fatal=False,
                    headers=self._HEADERS)
                channel_data = traverse_obj(channel_json, ('ex_content', {
                    'm3u8_url': ('streaming_url', {url_or_none}),
                    'title': ('title', {str}),
                    'thumbnail': ('thumbnail', 'url', {url_or_none}),
                }))
            else:  # video_type == 'broadcasts'
                channel_json = self._download_json(
                    f'https://survapi.channel.or.jp/ex/events/{channel_id}', channel_id,
                    'Getting live channel info', 'Unable to get live channel info', fatal=False,
                    headers=self._HEADERS, query={'embed': 'channel'})
                channel_data = traverse_obj(channel_json, ('data', {
                    'm3u8_url': ('Channel', 'Custom_live_url', {self._proto_relative_url}, {url_or_none}),
                    'title': ('Name', {str}),
                    'thumbnail': ('Poster_url', {url_or_none}),
                }))

            m3u8_url = channel_data.pop('m3u8_url')
            entries.append({
                'id': channel_id,
                'formats': self._extract_m3u8_formats(m3u8_url, channel_id, fatal=False),
                'is_live': video_type == 'broadcasts',
                **channel_data,
            })

        if not self._is_logged_in and not entries:
            self.raise_login_required()

        return self.playlist_result(
            entries, video_id, self._og_search_title(webpage))
