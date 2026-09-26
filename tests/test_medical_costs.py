import unittest

from medical_costs import estimate_outpatient_costs, medication_schedule


class InsuranceCostsTest(unittest.TestCase):
    def test_low_cost_and_no_insurance(self):
        result = estimate_outpatient_costs([10000]*12, age=60, copay=3, income="c")
        self.assertEqual(result["after"], 36000)
        self.assertEqual(result["total_relief"], 0)
        cash = estimate_outpatient_costs([1000000]*12, age=80, copay=10, income=None)
        self.assertEqual(cash["after"], 12000000)
        self.assertEqual(cash["total_relief"], 0)

    def test_fourth_hit_and_annual_cap(self):
        result = estimate_outpatient_costs([1000000]*12, age=60, copay=3, income="c")
        self.assertEqual(result["months"][0]["after_monthly"], 92940)
        self.assertEqual(result["months"][2]["after_monthly"], 92940)
        self.assertEqual(result["months"][3]["after_monthly"], 44400)
        self.assertEqual(result["after"], 530000)
        self.assertEqual(result["annual_relief"], 148420)

    def test_all_working_income_bands(self):
        expected = {"a":271290, "b":183130, "c":92940,
                    "d":61500, "d_low":61500, "e":36900}
        for income, cost in expected.items():
            result = estimate_outpatient_costs([1000000]+[0]*11, age=60, copay=3, income=income)
            self.assertEqual(result["after"], cost)
        low = estimate_outpatient_costs([1000000]*12, age=60, copay=3, income="d_low")
        self.assertEqual(low["after"], 410000)

    def test_elderly_outpatient_and_income_boundaries(self):
        for age, copay, income, expected in [(70,2,"general",216000),
                                            (75,1,"low2",96000),
                                            (80,1,"low1",96000)]:
            result = estimate_outpatient_costs([1000000]*12, age=age, copay=copay, income=income)
            self.assertEqual(result["after"], expected)
            self.assertFalse(any(m["multiple"] for m in result["months"]))
        active = estimate_outpatient_costs([1000000]*12, age=80, copay=3, income="c")
        self.assertEqual(active["after"], 530000)

    def test_unknown_and_invalid_inputs_do_not_generate_discount(self):
        for age,copay,income in [(60,3,None),(60,1,"e"),(80,3,"general"),(80,2,"low1")]:
            with self.assertRaises(ValueError):
                estimate_outpatient_costs([10000]*12,age=age,copay=copay,income=income)
        for costs in [[1]*11, [-1]*12, [float('nan')]*12]:
            with self.assertRaises(ValueError):
                estimate_outpatient_costs(costs,age=60,copay=3,income="c")
        with self.assertRaises(ValueError):
            medication_schedule([{"key":"unpriced", "annual_cost_yen":None}])

    def test_recent_hit_months_expire_and_zero_costs_are_not_hits(self):
        result = estimate_outpatient_costs([0,1000000]+[0]*10,age=60,copay=3,income="c",
                                           previous_hit_months=[-11,-10,-9])
        self.assertEqual(result["months"][1]["after_monthly"],92940)
        recent = estimate_outpatient_costs([1000000]+[0]*11,age=60,copay=3,income="c",
                                           previous_hit_months=[-3,-2,-1])
        self.assertEqual(recent["months"][0]["after_monthly"],44400)

    def test_below_21000_months_do_not_use_under70_annual_allowance(self):
        costs = [60000]*11+[1000000]
        result = estimate_outpatient_costs(costs,age=60,copay=3,income="e")
        self.assertEqual(result["annual_relief"],0)
        self.assertEqual(result["after"],11*18000+36900)

    def test_inclisiran_is_charged_in_injection_months(self):
        med={"key":"レクビオ（インクリシラン）284 mg 6か月ごと", "annual_cost_yen":789516}
        for first,indices in [(True,[0,3,9]),(False,[0,6])]:
            schedule=medication_schedule([med],inclisiran_first_year=first)["monthly_gross"]
            self.assertEqual([i for i,cost in enumerate(schedule) if cost],indices)
            self.assertEqual(sum(schedule),394758*len(indices))
        first=medication_schedule([med],inclisiran_first_year=True)["monthly_gross"]
        result=estimate_outpatient_costs(first,age=60,copay=3,income="c")
        self.assertAlmostEqual(result["after"],3*(85800+(394758-286000)*.01))
        self.assertFalse(any(m["multiple"] for m in result["months"]))

    def test_repatha_calendar_and_oral_cost_conservation(self):
        schedule=medication_schedule([{"key":"レパーサ140 mg 隔週注","annual_cost_yen":631852}])
        self.assertEqual(sum(schedule["monthly_gross"]),24302*27)
        self.assertEqual(schedule["monthly_gross"][0],24302*3)
        daily=medication_schedule([{"key":"メトホルミン 1000 mg","annual_cost_yen":7884}])
        self.assertAlmostEqual(sum(daily["monthly_gross"]),7884)
        self.assertAlmostEqual(daily["monthly_gross"][6],7884*28/365)


if __name__ == "__main__":
    unittest.main()
