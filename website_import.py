"""Bounded public-web import. No scripts, cookies or private-network access."""
import http.client
import ipaddress
import socket
import ssl
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit, quote


def public_url(url):
    url = str(url).strip()
    if '://' not in url:
        url = 'https://' + url
    p = urlsplit(url)
    if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password:
        raise ValueError('Nhập địa chỉ website http hoặc https công khai.')
    if p.port not in (None, 80, 443):
        raise ValueError('Website phải dùng cổng 80 hoặc 443.')
    host = p.hostname.encode('idna').decode('ascii')
    addresses = socket.getaddrinfo(host, p.port or (443 if p.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Chỉ lấy nội dung website công khai trên Internet.')
    netloc = host + ((':' + str(p.port)) if p.port else '')
    return urlunsplit((p.scheme, netloc, quote(p.path or '/', safe='/%:@'), quote(p.query, safe='=&%:+/?@'), '')), addresses[0][4][0]


def fetch_public(url, limit=4_000_000):
    for _ in range(6):
        url, ip = public_url(url)
        p = urlsplit(url)
        port = p.port or (443 if p.scheme == 'https' else 80)
        # Pin the validated address; HTTPS still verifies the original hostname.
        conn = http.client.HTTPConnection(p.hostname, port, timeout=15)
        sock = socket.create_connection((ip, port), timeout=15)
        try:
            if p.scheme == 'https':
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=p.hostname)
            conn.sock = sock
            conn.request('GET', p.path + ('?' + p.query if p.query else ''), headers={'User-Agent': 'VideoStudio/1.0', 'Accept-Encoding': 'identity'})
            r = conn.getresponse()
            if r.status in (301, 302, 303, 307, 308):
                url = urljoin(url, r.getheader('Location') or '')
                continue
            if r.status != 200:
                raise ValueError(f'Website trả lỗi {r.status}. Có thể trang chặn lấy nội dung tự động.')
            data = r.read(limit + 1)
            if len(data) > limit:
                raise ValueError('Tệp trên website quá lớn.')
            return data, r.getheader('Content-Type', ''), url
        finally:
            conn.close()
            sock.close()
    raise ValueError('Website chuyển hướng quá nhiều lần.')


class PageParser(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.texts, self.images, self.title, self.description = base, [], [], [], ''
        self.skip, self.in_title = [], False
        self.phones = []
        self.links, self._a = [], None

    def add_image(self, src, alt=''):
        if not src:
            return
        url = urljoin(self.base, src.strip())
        if urlsplit(url).scheme in ('http', 'https') and url not in [x['url'] for x in self.images]:
            self.images.append({'url': url, 'label': alt[:160]})

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('script', 'style', 'noscript', 'template'):
            self.skip.append(tag)
        if self.skip:
            return
        if tag == 'title':
            self.in_title = True
        if tag == 'a' and a.get('href'):
            self._a = [urljoin(self.base, a['href'].strip()), '']
            self.links.append(self._a)
        if tag == 'a' and a.get('href', '').lower().startswith('tel:'):
            phone = a['href'][4:].strip()
            if re.fullmatch(r'[+\d ().-]{6,30}', phone) and phone not in self.phones:
                self.phones.append(phone)
        if tag == 'meta':
            key = (a.get('property') or a.get('name') or '').lower()
            if key in ('description', 'og:description') and not self.description:
                self.description = a.get('content', '')
            if key in ('og:image', 'twitter:image'):
                self.add_image(a.get('content'))
        if tag == 'img':
            self.add_image(a.get('data-src') or a.get('data-lazy-src') or a.get('src'), a.get('alt', ''))
            if not a.get('src') and a.get('srcset'):
                self.add_image(a['srcset'].split(',')[-1].strip().split(' ')[0], a.get('alt', ''))

    def handle_endtag(self, tag):
        if self.skip and tag == self.skip[-1]:
            self.skip.pop()
        if tag == 'title':
            self.in_title = False
        if tag == 'a':
            self._a = None

    def handle_data(self, data):
        if self.skip:
            return
        text = ' '.join(data.split())
        if text:
            self.texts.append(text)
            if self._a is not None and len(self._a[1]) < 80:
                self._a[1] += ' ' + text
            if self.in_title:
                self.title.append(text)


ABOUT = re.compile(r'gioi-thieu|ve-chung-toi|about|ve-cong-ty|gioithieu|giới thiệu|về chúng tôi|về công ty', re.I)


def _page(url):
    raw, mime, final = fetch_public(url)
    if 'html' not in mime.lower():
        raise ValueError('Địa chỉ phải là trang web HTML.')
    charset = re.search(r'charset=["\s]*([\w-]+)', mime, re.I)
    encoding = charset.group(1) if charset else 'utf-8'
    try:
        html = raw.decode(encoding, errors='replace')
    except LookupError:
        html = raw.decode('utf-8', errors='replace')
    parser = PageParser(final)
    parser.feed(html)
    return parser, final


def about_link(parser, final):
    """Trang giới thiệu cùng tên miền (nếu trang đang đọc có liên kết tới)."""
    host = urlsplit(final).hostname
    for href, label in parser.links:
        p = urlsplit(href)
        if p.scheme in ('http', 'https') and p.hostname == host and (ABOUT.search(p.path) or ABOUT.search(label)):
            clean = urlunsplit((p.scheme, p.netloc, p.path, p.query, ''))
            if clean.rstrip('/') != final.rstrip('/'):
                return clean
    return None


def read_website(url):
    parser, final = _page(url)
    text = parser.description + '\n' + '\n'.join(dict.fromkeys(parser.texts))
    images, phones, pages = list(parser.images), list(parser.phones), [final]
    # Đọc thêm trang giới thiệu để có năm thành lập, lĩnh vực, chi nhánh. Lỗi ở trang phụ không làm hỏng trang chính.
    more = about_link(parser, final)
    if more and not ABOUT.search(urlsplit(final).path):
        try:
            extra, extra_url = _page(more)
            seen = set(parser.texts)
            added = [x for x in dict.fromkeys(extra.texts) if x not in seen]
            if added:
                text = text[:8000] + '\n\n[Trang giới thiệu: ' + extra_url + ']\n' + '\n'.join(added)
                pages.append(extra_url)
            have = {x['url'] for x in images}
            images += [x for x in extra.images if x['url'] not in have]
            phones += [x for x in extra.phones if x not in phones]
        except Exception:  # noqa: BLE001
            pass
    return {'url': final, 'title': ' '.join(parser.title)[:200], 'text': text[:14000], 'images': images[:36], 'phones': phones[:5], 'pages': pages}


def image_bytes(url):
    raw, mime, final = fetch_public(url, 12_000_000)
    if not mime.lower().startswith('image/'):
        raise ValueError('Đường dẫn không trả về ảnh.')
    # Decode with Pillow before saving; reject SVG/HTML and decompression bombs.
    from PIL import Image
    from io import BytesIO
    with Image.open(BytesIO(raw)) as im:
        if im.width * im.height > 25_000_000:
            raise ValueError('Ảnh quá lớn (tối đa 25 triệu điểm ảnh).')
        im.load()
        out = BytesIO()
        im.convert('RGBA').save(out, format='PNG')
        return out.getvalue(), final
