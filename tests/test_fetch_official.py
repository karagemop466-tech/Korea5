"""Offline regression tests for official-source acquisition.

Fixtures are deliberately synthetic: these tests exercise parser behavior, not
live-source truth or game availability. Live official pages are cited in the
feed audit; only a successful source refresh can establish current data.
"""
import datetime as dt
import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from tools import fetch_official as feed


def nfl_page(*games, season=2026, season_type="REG", week=9):
    query = {
        "queryKey": ["useFetchFootballWeeklyGameDetails", {
            "season": str(season), "seasonType": season_type, "week": week,
        }],
        "state": {"data": list(games)},
    }
    payload = [1, "1:" + json.dumps({"queries": [query]})]
    return "<script>self.__next_f.push(" + json.dumps(payload) + ")</script>"


def nfl_game(**overrides):
    game = {
        "id": "abc", "season": 2026, "seasonType": "REG", "week": 9,
        "awayTeam": {"fullName": "San Francisco 49ers"},
        "homeTeam": {"fullName": "Baltimore Ravens"},
        "time": "2026-11-06T01:15:00Z", "status": "SCHEDULED",
        "broadcastInfo": {"audioNetworks": [{"audience": "AUDIO_NETWORK_AUDIENCE_WESTWOOD_ONE"}]},
        "externalIds": [{"source": "slug", "id": "49ers-at-ravens-2026-reg-9"}],
    }
    game.update(overrides)
    return game


def grid(*ids, extra=""):
    rows = "".join(
        '<div class="event"><div class="date">NOV 05</div>'
        f'<div class="name"><a href="/events/{i}">Game &amp; {i}</a></div>'
        '<div class="venue">A venue</div><div class="description">A listing</div></div>'
        for i in ids
    )
    return f'<div id="eventCalendar_more"><div class="events">{rows}</div></div>{extra}'


def station_panel(sport, caption, rows):
    body = "".join(f"<tr><td>{city}</td><td>{call}</td></tr>" for city, call in rows)
    return (
        '<div class="vc_tta-panel"><div class="vc_tta-panel-heading">'
        f'<span class="vc_tta-title-text">{sport}</span></div>'
        f'<div><table><caption><b>{caption}</b></caption><tbody>{body}</tbody></table></div></div>'
    )


class PacificTimeTests(unittest.TestCase):
    def test_dst_spring_transition(self):
        self.assertEqual(feed.pt_parts("2027-03-14T09:59:00Z"), ("2027-03-14", "01:59", "PST"))
        self.assertEqual(feed.pt_parts("2027-03-14T10:01:00Z"), ("2027-03-14", "03:01", "PDT"))

    def test_utc_to_previous_pacific_date(self):
        self.assertEqual(feed.pt_parts("2026-11-06T01:15:00Z"), ("2026-11-05", "17:15", "PST"))

    def test_naive_and_invalid_times_are_not_assumed_utc(self):
        for value in ("2026-11-06T01:15:00", "not a timestamp", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                feed.pt_parts(value)


class NFLParsingTests(unittest.TestCase):
    def test_requested_week_and_pacific_time(self):
        with patch.object(feed, "get", return_value=nfl_page(nfl_game())):
            games, errors, _ = feed.fetch_nfl_week((2026, "week-9", "Week 9"))
        self.assertEqual(errors, [])
        self.assertEqual(len(games), 1)
        self.assertEqual((games[0]["datePT"], games[0]["startPT"]), ("2026-11-05", "17:15"))
        self.assertEqual(games[0]["timeStatus"], "verified")
        self.assertEqual(games[0]["priority"], "high")
        self.assertIn("Westwood", games[0]["nationalRadio"])

    def test_wrong_season_or_week_is_not_relabelled(self):
        page = nfl_page(nfl_game())
        with patch.object(feed, "get", return_value=page):
            for item in ((2027, "week-9", "Week 9"), (2026, "week-8", "Week 8")):
                games, errors, _ = feed.fetch_nfl_week(item)
                self.assertEqual(games, [])
                self.assertTrue(errors)

    def test_foreign_game_inside_matching_query_is_rejected(self):
        page = nfl_page(nfl_game(week=10))
        with patch.object(feed, "get", return_value=page):
            games, errors, _ = feed.fetch_nfl_week((2026, "week-9", "Week 9"))
        self.assertEqual(games, [])
        self.assertTrue(any("does not match" in e for e in errors))

    def test_tbd_stays_blank(self):
        with patch.object(feed, "get", return_value=nfl_page(nfl_game(time=None))):
            games, errors, _ = feed.fetch_nfl_week((2026, "week-9", "Week 9"))
        self.assertEqual(errors, [])
        self.assertIsNone(games[0]["startPT"])
        self.assertIsNone(games[0]["datePT"])
        self.assertEqual(games[0]["timeStatus"], "unverified")

    def test_invalid_time_does_not_get_verified(self):
        with patch.object(feed, "get", return_value=nfl_page(nfl_game(time="2026-11-06T01:15:00"))):
            games, errors, _ = feed.fetch_nfl_week((2026, "week-9", "Week 9"))
        self.assertTrue(errors)
        self.assertIsNone(games[0]["startUTC"])
        self.assertEqual(games[0]["timeStatus"], "unverified")

    def test_empty_postseason_query_is_not_an_invented_matchup(self):
        with patch.object(feed, "get", return_value=nfl_page(season_type="POST", week=1)):
            games, errors, _ = feed.fetch_nfl_week((2026, "wild-card-weekend", "Wild Card Weekend"))
        self.assertEqual((games, errors), ([], []))

    def test_url_falls_back_to_official_week_if_game_slug_is_unsafe(self):
        g = nfl_game(externalIds=[{"source": "slug", "id": "../../outside"}])
        with patch.object(feed, "get", return_value=nfl_page(g)):
            games, errors, url = feed.fetch_nfl_week((2026, "week-9", "Week 9"))
        self.assertEqual(errors, [])
        self.assertEqual(games[0]["sourceUrl"], url)


class WestwoodGridAndEventTests(unittest.TestCase):
    def test_grid_excludes_sidebar_and_decodes_entities(self):
        sidebar = '<div class="event"><a href="/events/999">Unrelated</a></div>'
        rows, error = feed.parse_w1_grid_checked(grid(123, extra=sidebar))
        self.assertIsNone(error)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["eventId"], "123")
        self.assertEqual(rows[0]["title"], "Game & 123")

    def test_missing_grid_or_missing_event_id_is_reported(self):
        self.assertIsNotNone(feed.parse_w1_grid_checked("<html>error</html>")[1])
        bad = '<div id="eventCalendar_more"><div class="event">No link</div></div>'
        self.assertIsNotNone(feed.parse_w1_grid_checked(bad)[1])

    def test_pagination_does_not_stop_after_four_hundred(self):
        offsets = []

        def fake_get(url, **_kwargs):
            if "/more/eventGrid/" in url:
                query = parse_qs(urlparse(url).query)
                offset = int(query["offset"][0])
                offsets.append(offset)
                # 3 full pages followed by a partial fourth page.
                return grid(*(str(100 + offset + i) for i in range(2 if offset < 6 else 1)))
            return '<span data-time="1793923200" class="start_time"></span>' \
                   '<span class="end_time" data-time="1793930400"></span>'

        with patch.object(feed, "W1_WIDGETS", {"NFL": ("unused", 1)}), \
                patch.object(feed, "W1_PAGE_SIZE", 2), patch.object(feed, "W1_MAX_PAGES", 5), \
                patch.object(feed, "get", side_effect=fake_get), patch.object(feed.time, "sleep"):
            events, _, errors = feed.fetch_w1()
        self.assertEqual(errors, [])
        self.assertEqual(len(events), 7)
        self.assertIn(6, offsets)

    def test_pagination_guard_reports_truncation(self):
        def fake_get(url, **_kwargs):
            if "/more/eventGrid/" in url:
                return grid("123")
            return '<span class="start_time" data-time="1793923200"></span>'
        with patch.object(feed, "W1_WIDGETS", {"NFL": ("unused", 1)}), \
                patch.object(feed, "W1_PAGE_SIZE", 1), patch.object(feed, "W1_MAX_PAGES", 2), \
                patch.object(feed, "get", side_effect=fake_get), patch.object(feed.time, "sleep"):
            _, _, errors = feed.fetch_w1()
        self.assertTrue(any("pagination limit" in e for e in errors))

    def test_missing_start_with_end_does_not_crash_or_invent_time(self):
        rec = feed.parse_w1_detail("1", "NFL", {}, '<span class="end_time" data-time="1793930400"></span>')
        self.assertIsNone(rec["startPT"])
        self.assertIsNone(rec["durationMin"])
        self.assertEqual(rec["timeStatus"], "unverified")
        self.assertIsNotNone(rec["endUTC"])

    def test_end_before_start_is_not_accepted(self):
        page = '<span class="start_time" data-time="1793930400"></span>' \
               '<span class="end_time" data-time="1793923200"></span>'
        rec = feed.parse_w1_detail("1", "NFL", {}, page)
        self.assertIsNone(rec["endUTC"])
        self.assertIsNone(rec["durationMin"])
        self.assertTrue(rec["parseErrors"])
        self.assertNotEqual(rec["verification"], "verified")

    def test_attr_order_and_overnight_listed_window(self):
        page = '<span data-time="1793923200" class="start_time"></span>' \
               '<span data-time="1793930400" class="end_time"></span>'
        rec = feed.parse_w1_detail("1", "NFL", {}, page)
        self.assertEqual(rec["durationMin"], 120)
        self.assertEqual(rec["endStatus"], "published-event-end")
        self.assertEqual(rec["verification"], "verified")


class StationParsingTests(unittest.TestCase):
    def test_sport_vintage_and_analog_caveats_are_retained(self):
        page = station_panel("NFL", "NFL Regular Season (2025)", [
            ("San Francisco, CA", "KNBR-AM"), ("San Francisco, CA", "KNBR-F2"),
        ]) + station_panel("Soccer", "USA Soccer (2025)", [
            ("San Francisco, CA", "KTCT-AM"), ("San Francisco, CA", "KTCT-AM"),
            ("Not San Francisco, CA", "OTHER-AM"),
        ])
        pack = feed.parse_w1_stations(page)
        self.assertEqual(pack["parseErrors"], [])
        self.assertEqual(len(pack["affiliates"]), 3)
        sport = {x["sport"]: x for x in pack["sportLists"]}
        self.assertEqual(sport["Soccer"]["callLetters"], ["KTCT-AM"])
        self.assertEqual(sport["NFL"]["caption"], "NFL Regular Season (2025)")
        digital = next(x for x in pack["affiliates"] if x["callLetters"] == "KNBR-F2")
        self.assertEqual(digital["analogReception"], "unverified")
        self.assertIn("analog", digital["receiverNote"])

    def test_missing_markup_is_not_a_valid_empty_station_list(self):
        self.assertTrue(feed.parse_w1_stations("<html>temporarily unavailable</html>")["parseErrors"])


class MLBFlagsTests(unittest.TestCase):
    def test_missing_tbd_is_unknown_not_false(self):
        page = json.dumps({"dates": [{"games": [
            {"gamePk": 1, "status": {"startTimeTBD": True}},
            {"gamePk": 2, "status": {"startTimeTBD": False}},
            {"gamePk": 3, "status": {}},
            {"gamePk": 4, "status": {"startTimeTBD": "false"}},
        ]}]})
        with patch.object(feed, "get", return_value=page):
            result, errors = feed.fetch_mlb_tbd((2027,))
        self.assertIs(result["flags"]["1"]["startTimeTBD"], True)
        self.assertIs(result["flags"]["2"]["startTimeTBD"], False)
        self.assertIsNone(result["flags"]["3"]["startTimeTBD"])
        self.assertIsNone(result["flags"]["4"]["startTimeTBD"])
        self.assertTrue(errors)

    def test_invalid_response_is_not_an_empty_schedule(self):
        with patch.object(feed, "get", return_value='{"message":"error"}'):
            _, errors = feed.fetch_mlb_tbd((2028,))
        self.assertEqual(len(errors), 10)

    def test_genuine_empty_dates_are_preserved_as_unknown_not_release_claim(self):
        with patch.object(feed, "get", return_value='{"dates":[]}'):
            result, errors = feed.fetch_mlb_tbd((2028,))
        self.assertEqual(errors, [])
        self.assertEqual(result["flags"], {})
        self.assertNotIn("not been released", result["note"])


class RefreshSafetyTests(unittest.TestCase):
    def test_failed_source_does_not_replace_any_snapshot(self):
        with patch.object(feed, "NFL_WEEK_SLUGS", [("week-1", "Week 1")]), \
                patch.object(feed, "fetch_nfl_week", return_value=([{"id": "x"}], [], "official")), \
                patch.object(feed, "fetch_w1", return_value=([], [], ["grid failed"])), \
                patch.object(feed, "fetch_w1_stations", return_value={"affiliates": [{}], "parseErrors": []}), \
                patch.object(feed, "fetch_mlb_tbd", return_value=({"flags": {"1": {}}}, [])), \
                patch.object(feed, "jwrite") as write:
            result = feed.main()
        self.assertEqual(result, 1)
        write.assert_not_called()

    def test_success_writes_all_feeds_only_after_checks(self):
        with patch.object(feed, "NFL_WEEK_SLUGS", [("week-1", "Week 1")]), \
                patch.object(feed, "fetch_nfl_week", return_value=([{"id": "x"}], [], "official")), \
                patch.object(feed, "fetch_w1", return_value=([{"id": "w1"}], ["official"], [])), \
                patch.object(feed, "fetch_w1_stations", return_value={"affiliates": [{}], "parseErrors": []}), \
                patch.object(feed, "fetch_mlb_tbd", return_value=({"flags": {"1": {}}}, [])), \
                patch.object(feed, "jwrite") as write:
            result = feed.main()
        self.assertEqual(result, 0)
        self.assertEqual([c.args[0] for c in write.call_args_list], [
            "nfl-2026.json", "westwoodone.json", "w1-stations.json", "mlb-tbd.json", "fetch-report.json",
        ])


if __name__ == "__main__":
    unittest.main()
