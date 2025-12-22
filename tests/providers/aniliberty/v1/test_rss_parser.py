from providers.aniliberty.v1.xml_parser import parse_torrents_rss

def test_parse_rss_basic():
    xml = b"""<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>Test</title>
        <item>
          <title>Item1</title>
          <link>http://example.com</link>
          <guid>abc</guid>
          <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
          <enclosure url="http://example.com/a.torrent" length="123" type="application/x-bittorrent"/>
        </item>
      </channel>
    </rss>"""
    out = parse_torrents_rss(xml)
    assert out["channel"]["title"] == "Test"
    assert len(out["items"]) == 1
    assert out["items"][0]["enclosure"]["url"].endswith(".torrent")
