import unittest
from unittest.mock import patch
import ticket_watch

PREFIX = '<html><body><h1>Avengers: Doomsday at Gurugram Pepsi PVR Ambience</h1><p>17 shows listed on BookMyShow</p><ul>'
SUFFIX = '</ul></body></html>'

class Tests(unittest.TestCase):
    def test_date_17_only(self):
        html = PREFIX + '<li>Thu 17 Dec, 06:20 AM · English • MS InfVsn ICE 3D · ICE</li>' + SUFFIX
        self.assertEqual(ticket_watch.parse_listing(html), ([], 1))

    def test_18_ice_3d_detected(self):
        s = 'Fri 18 Dec, 07:35 PM · English • MS InfVsn ICE 3D · ICE'
        html = PREFIX + '<li>' + s + '</li>' + SUFFIX
        self.assertEqual(ticket_watch.parse_listing(html), ([s], 1))

    def test_other_formats_ignored(self):
        html = PREFIX + '<li>Fri 18 Dec, 07:35 PM · English • MS - Inf Vsn 4DX 3D · 4DX</li><li>Fri 18 Dec, 08:30 PM · English • MS - Infinity Vision</li>' + SUFFIX
        self.assertEqual(ticket_watch.parse_listing(html), ([], 2))

    def test_unexpected_page_raises(self):
        with self.assertRaises(ticket_watch.ListingError):
            ticket_watch.parse_listing('<html><body>Access Denied</body></html>')

    def test_missing_rows_raises(self):
        with self.assertRaises(ticket_watch.ListingError):
            ticket_watch.parse_listing(PREFIX + SUFFIX)

    def test_no_shows_valid(self):
        html = PREFIX.replace('17 shows listed', '0 shows listed') + SUFFIX
        self.assertEqual(ticket_watch.parse_listing(html), ([], 0))

    def test_manual_check_never_sends_or_disables(self):
        html = PREFIX + '<li>Fri 18 Dec, 07:35 PM · English • MS InfVsn ICE 3D · ICE</li>' + SUFFIX
        with patch.object(ticket_watch, 'fetch_listing', return_value=html), patch.object(ticket_watch, 'telegram_message') as msg, patch.object(ticket_watch, 'disable_own_workflow') as dis:
            self.assertEqual(ticket_watch.run(automated=False), 0)
            msg.assert_not_called()
            dis.assert_not_called()

if __name__ == '__main__':
    unittest.main()
