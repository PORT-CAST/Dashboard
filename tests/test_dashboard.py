"""로컬 CSV와 Streamlit 화면의 분석 기준·입력 경계를 검증한다. 외부 API 호출 없음."""
import logging
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
logging.disable(logging.CRITICAL)
import kpi
import models
import ui


class AnalysisTests(unittest.TestCase):
    def test_cohort_boundaries_and_terminal_ownership(self):
        table = pd.DataFrame({
            "터미널": ["BPT_S"] * 4 + ["PNC"] * 4 + ["unknown"],
            "GT": [5000, 9999, 10000, 4999, 100000, 149999, 150000, 99999, 5000],
            "작업량": [400, 600, 500, 500, 2000, 2500, 2200, 2200, 500],
        })
        self.assertEqual(kpi.거르기(table, 조건부="항만별").index.tolist(), [0, 1, 4, 5])
        common = pd.DataFrame({
            "터미널": ["BPT_S", "PNC", "HPNT", "BNCT", "unknown"],
            "GT": [10000, 19999, 20000, 15000, 15000],
            "작업량": [600, 800, 700, 801, 700],
        })
        self.assertEqual(kpi.거르기(common, 조건부="공통").index.tolist(), [0, 1])
        self.assertEqual(len(kpi.거르기(common)), 5)

    def test_port_cohort_matches_late_eda(self):
        for table in kpi.불러오기():
            sample = kpi.거르기(table, 조건부="항만별")
            self.assertEqual(len(sample), 5395)
            self.assertEqual(sample.groupby("터미널").size().to_dict(), {
                "BNCT": 176, "HPNT": 119, "PNC": 108,
                "PNIT": 93, "BPTC_G": 1478, "BPT_S": 3421,
            })

    def test_common_cohort_matches_early_eda(self):
        """노트북 앞부분: 6개 터미널 공통 GT 1만~2만 미만·작업량 600~800 (887건, 터미널별 47~280건)."""
        for table in kpi.불러오기():
            sample = kpi.거르기(table, 조건부="공통")
            self.assertEqual(len(sample), 887)
            self.assertEqual(sample.groupby("터미널").size().to_dict(), {
                "BNCT": 126, "HPNT": 47, "PNC": 130,
                "PNIT": 54, "BPTC_G": 250, "BPT_S": 280,
            })

    def test_weather_bin_boundaries(self):
        waves = pd.DataFrame({"파고": [0., .499, .5, 1., 2.]})
        self.assertEqual(kpi.구간나누기(waves, "유의파고").astype(str).tolist(),
                         ["0.5 미만", "0.5 미만", "0.5~1", "1~2", "2 이상"])
        visibility = pd.DataFrame({"시정": [0., 4.99, 5., 10., 30.]})
        self.assertEqual(kpi.구간나누기(visibility, "시정").astype(str).tolist(),
                         ["5 미만", "5 미만", "5~10", "10~30", "30 이상"])

    def test_neighbors_use_distance_and_new_values(self):
        table = pd.DataFrame({"x": [0., 1., 2., 3., 100., 101., 102.],
                              "y": [1000., 1001., 1002., 1003., 1100., 1101., 1102.]})
        self.assertEqual(models.조건예측(table, "x", "y", 4., "ge", 4), 1001.5)
        changed = table.assign(y=table["y"] + 100.)
        self.assertEqual(models.조건예측(changed, "x", "y", 4., "ge", 4), 1101.5)

    def test_original_regression_results_are_preserved(self):
        one = models.불러오기("KPI1")[0]
        two = models.불러오기("KPI2")[0]
        self.assertEqual(one.nobs, 32014)
        self.assertEqual(two.nobs, 23557)
        self.assertAlmostEqual(one.rsquared, .7352058329684932)
        self.assertAlmostEqual(two.rsquared, .7502434956757779)
        alert = models.특보효과(two).set_index("터미널").loc["BPT_S"]
        self.assertAlmostEqual(alert["효과"], 1.092505, places=5)
        self.assertAlmostEqual(alert["하한"], .212002, places=5)
        self.assertAlmostEqual(alert["상한"], 1.973008, places=5)

    def test_model_rejects_impossible_weather(self):
        one, frame, _ = models.불러오기()
        profiles = models.시나리오프로필(frame)
        values = models.평온기준(frame, profiles, "BPT_S")
        values[models.기상변수[0]] = 1.
        values[models.기상변수[1]] = 0.
        with self.assertRaises(ValueError):
            models.조절효과(one, profiles, "BPT_S", values, False)


class ScreenTests(unittest.TestCase):
    def setUp(self):
        self.payloads = []
        self.capture = patch.object(ui, "AI요약칸", self.payloads.append)
        self.capture.start()
        self.addCleanup(self.capture.stop)
        self.app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()

    def open_check(self):
        self.app.button(key="메뉴_기상 상황 점검").click().run()
        self.assertFalse(self.app.exception)

    def test_first_check_visit_has_summary_input(self):
        self.open_check()
        self.assertTrue(self.payloads[-1]["분석결과"])
        self.assertEqual(self.payloads[-1]["터미널"], "BPT_S")

    def test_summary_uses_current_unrounded_weather(self):
        self.open_check()
        self.app.slider(key="점검_체류시간_최대순간풍속_최댓값_mps").set_value(9.).run()
        frame = models.불러오기()[1]
        expected = models.조건예측(frame, models.기상변수[1], models.기상변수[0], 9., "le")
        value = self.payloads[-1]["분석결과"]["설정 기상값"]["풍속 중앙값"]
        self.assertAlmostEqual(value, expected)

    def test_zero_gust_cannot_have_positive_median(self):
        self.open_check()
        self.app.toggle(key="점검_세부").set_value(True).run()
        self.app.slider(key="점검_체류시간_최대순간풍속_최댓값_mps").set_value(0.).run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.session_state["점검_체류시간_풍속_중앙값_mps"], 0.)

    def test_empty_month_does_not_crash(self):
        self.app.button(key="메뉴_KPI 1").click().run()
        self.app.session_state["기간선택"] = "2021"
        for month in range(1, 13):
            self.app.session_state[f"k1_m{month}"] = month == 1
        self.app.run()
        self.assertFalse(self.app.exception)
        graph = self.payloads[-1]["분석결과"]["월 선택 비교 그래프"]
        self.assertEqual(graph["단순 차이"], [])
        self.assertEqual(graph["월"], "1월")

    def test_year_terminal_and_weather_filters(self):
        for page in ["KPI 1", "KPI 2"]:
            self.app.button(key="메뉴_" + page).click().run()
            for year in ["2021", "2022", "2023", "2024"]:
                for terminal in kpi.터미널순서:
                    self.app.session_state["기간선택"] = year
                    self.app.session_state["북항선택"] = terminal if terminal.startswith("BPT") else None
                    self.app.session_state["신항선택"] = None if terminal.startswith("BPT") else terminal
                    self.app.run()
                    self.assertFalse(self.app.exception, (page, year, terminal))
        self.app.button(key="메뉴_KPI 1").click().run()
        for variable in kpi.기상구간:
            self.app.session_state["기상변수선택"] = variable
            self.app.run()
            self.assertFalse(self.app.exception, variable)

    def _tiles(self):
        return " ".join(m.value for m in self.app.markdown if "tile" in m.value)

    def test_default_sample_matches_presentation_numbers(self):
        """첫 화면 기본값(6개 터미널 공통)에서 발표 대본 숫자가 그대로 나온다."""
        self.app.button(key="메뉴_KPI 1").click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.session_state["표본선택"], "6개 터미널 공통")
        self.assertIn("+4.0h", self._tiles())
        self.assertIn("+3.8~+6.1h", self._tiles())
        self.app.button(key="메뉴_KPI 2").click().run()
        self.assertIn("+1.8h", self._tiles())
        self.assertIn("+0.2~+1.1h", self._tiles())
        self.app.session_state["표본선택"] = "항만별"
        self.app.run()
        self.assertFalse(self.app.exception)
        self.assertIn("+1.5h", self._tiles())
        self.app.session_state["표본선택"] = "전체 표본"
        self.app.run()
        self.assertFalse(self.app.exception)

    def test_return_to_check_keeps_settings(self):
        """다른 화면에 다녀와도 오류 없이 마지막 설정이 유지된다."""
        self.open_check()
        self.app.button(key="점검_프리셋_폭풍급").click().run()
        self.app.toggle(key="점검_특보").set_value(True).run()
        키 = "점검_체류시간_최대순간풍속_최댓값_mps"
        전 = self.app.session_state[키]
        for 화면 in ["KPI 1", "KPI 2", "전체 요약"]:
            self.app.button(key="메뉴_" + 화면).click().run()
            self.open_check()
            self.assertEqual(self.app.session_state[키], 전)
            self.assertTrue(self.app.session_state["점검_특보"])

    def test_presets_and_extreme_inputs(self):
        self.open_check()
        for terminal in kpi.터미널순서:
            self.app.selectbox(key="점검_터미널").select(terminal).run()
            for name in models.시나리오정의:
                self.app.button(key="점검_프리셋_" + name).click().run()
                self.assertFalse(self.app.exception, (terminal, name))
        self.app.toggle(key="점검_세부").set_value(True).run()
        for variable, bounds in models.주변수범위.items():
            for edge in bounds[:2]:
                self.app.slider(key="점검_" + variable).set_value(edge).run()
                self.assertFalse(self.app.exception, (variable, edge))


class SummaryTests(unittest.TestCase):
    def test_missing_files_keep_all_pages_open(self):
        missing = ROOT / "data" / "does_not_exist.csv"
        with patch.object(kpi, "KPI1파일", missing), patch.object(kpi, "KPI2파일", missing):
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
            for page in ["전체 요약", "KPI 1", "KPI 2", "기상 상황 점검"]:
                app.button(key="메뉴_" + page).click().run()
                self.assertFalse(app.exception)
                self.assertTrue(app.button(key="ai_btn").disabled)

    def test_missing_key_does_not_call_google(self):
        code = 'import ui\nui.AI요약칸({"분석결과": [{"건수": 1}]})'
        app = AppTest.from_string(code, default_timeout=15)
        app.secrets["GEMINI_API_KEY"] = ""
        with patch.object(ui.genai, "Client") as client:
            app.run().button(key="ai_btn").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
