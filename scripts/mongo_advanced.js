// Advanced MongoDB features described in the final report (section 3, non-relational part).
// Run after an import:  mongosh "mongodb://localhost:27017/quant" scripts/mongo_advanced.js
// Idempotent. news and notes are created by the application; the other three collections here.

const show = (label, cursor) => { print(`\n== ${label}`); printjson(cursor.toArray ? cursor.toArray() : cursor); };

// --- Collections 3-5: schemas and indexes -----------------------------------------------

// sentiment_monthly: materialised aggregate of news (rebuilt by $merge below).
db.sentiment_monthly.createIndex({ ticker: 1, month: 1 }, { unique: true });

// sector_profiles: one document per sector; sector-specific KPI fields vary, so only the core is validated.
if (!db.getCollectionNames().includes('sector_profiles')) {
  db.createCollection('sector_profiles', { validator: { $jsonSchema: {
    bsonType: 'object', required: ['sector', 'kpis'],
    properties: { sector: { bsonType: 'string' }, kpis: { bsonType: 'array', items: { bsonType: 'object', required: ['key', 'label'] } } } } } });
}
db.sector_profiles.createIndex({ sector: 1 }, { unique: true });

// activity_logs: append-only research activity; TTL index expires entries after 90 days.
if (!db.getCollectionNames().includes('activity_logs')) {
  db.createCollection('activity_logs', { validator: { $jsonSchema: {
    bsonType: 'object', required: ['user_id', 'action', 'ts'],
    properties: { user_id: { bsonType: 'int' }, action: { bsonType: 'string' }, ts: { bsonType: 'date' } } } } });
}
db.activity_logs.createIndex({ ts: 1 }, { expireAfterSeconds: 60 * 60 * 24 * 90 });
db.activity_logs.createIndex({ user_id: 1, ts: -1 });

// Text index for headline keyword search on the feed.
db.news.createIndex({ title: 'text' }, { name: 'news_title_text' });

// --- A1 Materialise monthly sentiment per ticker with $merge (incremental "materialised view") -------
db.news.aggregate([
  { $group: {
      _id: { ticker: '$ticker', month: { $dateTrunc: { date: '$date', unit: 'month' } } },
      articles: { $sum: 1 },
      avg_sentiment: { $avg: '$sentiment' },
      positive: { $sum: { $cond: [{ $gt: ['$sentiment', 0] }, 1, 0] } },
      negative: { $sum: { $cond: [{ $lt: ['$sentiment', 0] }, 1, 0] } },
      publishers: { $addToSet: '$publisher' } } },
  { $project: { _id: 0, ticker: '$_id.ticker', month: '$_id.month', articles: 1, avg_sentiment: 1,
      positive: 1, negative: 1, publisher_count: { $size: '$publishers' }, refreshed_at: '$$NOW' } },
  { $merge: { into: 'sentiment_monthly', on: ['ticker', 'month'], whenMatched: 'replace', whenNotMatched: 'insert' } }
]);
print('sentiment_monthly documents:', db.sentiment_monthly.countDocuments());

// --- A2 Rolling 7-day sentiment for one ticker ($setWindowFields with a time-range window) ----------
show('A2 AAPL rolling 7-day sentiment', db.news.aggregate([
  { $match: { ticker: 'AAPL' } },
  { $group: { _id: { $dateTrunc: { date: '$date', unit: 'day' } }, daily: { $avg: '$sentiment' }, n: { $sum: 1 } } },
  { $setWindowFields: { sortBy: { _id: 1 }, output: {
      rolling7: { $avg: '$daily', window: { range: [-6, 0], unit: 'day' } },
      articles7: { $sum: '$n', window: { range: [-6, 0], unit: 'day' } } } } },
  { $sort: { _id: -1 } }, { $limit: 10 }
]));

// --- A3 One-round-trip feed dashboard ($facet + $bucket) --------------------------------------------
show('A3 March 2020 feed dashboard', db.news.aggregate([
  { $match: { date: { $gte: ISODate('2020-03-01'), $lt: ISODate('2020-04-01') } } },
  { $facet: {
      latest: [{ $sort: { date: -1 } }, { $limit: 5 }, { $project: { _id: 0, ticker: 1, title: 1, date: 1, sentiment: 1 } }],
      by_publisher: [{ $group: { _id: '$publisher', n: { $sum: 1 }, avg: { $avg: '$sentiment' } } }, { $sort: { n: -1 } }, { $limit: 5 }],
      distribution: [{ $bucket: { groupBy: '$sentiment', boundaries: [-1, -0.33, 0.33, 1.000001], default: 'other',
                                  output: { n: { $sum: 1 } } } }],
      most_bearish: [{ $group: { _id: '$ticker', avg: { $avg: '$sentiment' }, n: { $sum: 1 } } },
                     { $match: { n: { $gte: 20 } } }, { $sort: { avg: 1 } }, { $limit: 5 }]
  } }
]));

// --- A4 Sentiment shock detection: months where sentiment drops >0.3 below the ticker's trailing 3-month mean
show('A4 sentiment shocks', db.sentiment_monthly.aggregate([
  { $match: { articles: { $gte: 10 } } },
  { $setWindowFields: { partitionBy: '$ticker', sortBy: { month: 1 }, output: {
      trailing: { $avg: '$avg_sentiment', window: { documents: [-3, -1] } } } } },
  { $match: { $expr: { $lt: ['$avg_sentiment', { $subtract: ['$trailing', 0.3] }] } } },
  { $project: { _id: 0, ticker: 1, month: 1, articles: 1, avg_sentiment: 1, trailing: 1 } },
  { $sort: { month: -1 } }, { $limit: 10 }
]));

// --- A5 Research watch-list digest: notes joined with recent sentiment ($lookup with a sub-pipeline) -
show('A5 notes + recent sentiment', db.notes.aggregate([
  { $group: { _id: '$ticker', notes: { $sum: 1 }, last_note: { $max: '$updated_at' } } },
  { $lookup: { from: 'sentiment_monthly', let: { t: '$_id' }, as: 'recent_sentiment', pipeline: [
      { $match: { $expr: { $eq: ['$ticker', '$$t'] } } }, { $sort: { month: -1 } }, { $limit: 3 },
      { $project: { _id: 0, month: 1, avg_sentiment: 1, articles: 1 } }] } },
  { $sort: { last_note: -1 } }
]));

// --- A6 Relevance-ranked keyword search on headlines ($text + textScore) ----------------------------
show('A6 BA downgrade headlines', db.news.find(
  { $text: { $search: 'downgrade downgrades' }, ticker: 'BA' },
  { _id: 0, title: 1, date: 1, sentiment: 1, score: { $meta: 'textScore' } }
).sort({ score: { $meta: 'textScore' } }).limit(5));
