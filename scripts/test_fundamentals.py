"""Cutoff and period matching tests for SEC extraction; no network required."""
import unittest
from fetch_fundamentals import extract

def fact(start,end,value,filed='2020-02-01'):
    return {'start':start,'end':end,'val':value,'filed':filed,'accn':'fixture-'+filed,'form':'10-K'}

def payload():
    return {'cik':1,'facts':{'us-gaap':{
      'Revenues':{'units':{'USD':[fact('2018-01-01','2018-12-31',100),fact('2019-01-01','2019-12-31',120)]}},
      'NetIncomeLoss':{'units':{'USD':[fact('2019-01-01','2019-12-31',-12)]}}}}}

class ExtractionTests(unittest.TestCase):
    def test_matching_annual_periods_allow_losses(self):
        r=extract(payload(),'TEST','2020-06-05')
        self.assertEqual((r['revenue'],r['previous_revenue'],r['net_income']),(120,100,-12))
    def test_future_restatement_is_excluded(self):
        p=payload();p['facts']['us-gaap']['Revenues']['units']['USD'].append(fact('2019-01-01','2019-12-31',999,'2021-02-01'))
        self.assertEqual(extract(p,'TEST','2020-06-05')['revenue'],120)
    def test_quarterly_income_cannot_match_annual_revenue(self):
        p=payload();p['facts']['us-gaap']['NetIncomeLoss']['units']['USD']=[fact('2019-10-01','2019-12-31',10)]
        self.assertIsNone(extract(p,'TEST','2020-06-05'))
    def test_nonpositive_prior_revenue_rejected(self):
        p=payload();p['facts']['us-gaap']['Revenues']['units']['USD'][0]['val']=0
        self.assertIsNone(extract(p,'TEST','2020-06-05'))
    def test_stale_annual_period_rejected(self):
        self.assertIsNone(extract(payload(),'TEST','2023-06-05'))
if __name__=='__main__':unittest.main()
