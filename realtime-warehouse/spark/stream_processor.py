"""Validate, enrich, and route raw EMS events from Kafka with Spark Structured Streaming."""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    current_timestamp,
    from_json,
    lit,
    regexp_replace,
    to_date,
    try_to_timestamp,
    trim,
    when,
    struct,
    to_json,
)
from pyspark.sql.types import StringType, StructField, StructType


SOURCE_COLUMNS = (
    "INCIDENT_ID", "INCIDENT_DATETIME", "INITIAL_CALL_TYPE", "INITIAL_SEVERITY_LEVEL_CODE",
    "FINAL_CALL_TYPE", "FINAL_SEVERITY_LEVEL_CODE", "FIRST_ASSIGNMENT_DATETIME",
    "VALID_DISPATCH_RSPNS_TIME_INDC", "DISPATCH_RESPONSE_SECONDS_QY", "FIRST_ACTIVATION_DATETIME",
    "FIRST_ON_SCENE_DATETIME", "VALID_INCIDENT_RSPNS_TIME_INDC", "INCIDENT_RESPONSE_SECONDS_QY",
    "INCIDENT_TRAVEL_TM_SECONDS_QY", "FIRST_TO_HOSP_DATETIME", "FIRST_HOSP_ARRIVAL_DATETIME",
    "INCIDENT_CLOSE_DATETIME", "HELD_INDICATOR", "INCIDENT_DISPOSITION_CODE", "BOROUGH",
    "INCIDENT_DISPATCH_AREA", "ZIPCODE", "POLICEPRECINCT", "CITYCOUNCILDISTRICT",
    "COMMUNITYDISTRICT", "COMMUNITYSCHOOLDISTRICT", "CONGRESSIONALDISTRICT", "REOPEN_INDICATOR",
    "SPECIAL_EVENT_INDICATOR", "STANDBY_INDICATOR", "TRANSFER_INDICATOR",
)

schema = StructType([StructField(name, StringType(), True) for name in SOURCE_COLUMNS])

spark = (
    SparkSession.builder.appName("ems-incident-stream")
    .config("spark.sql.session.timeZone", "UTC")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")

raw = (
    spark.readStream.format("kafka")
    .option("kafka.bootstrap.servers", "kafka:9092")
    .option("subscribe", "ems.incidents.raw")
    .option("startingOffsets", "earliest")
    .option("failOnDataLoss", "true")
    .load()
)

parsed = raw.select(from_json(col("value").cast("string"), schema).alias("s")).select("s.*")
timestamp_format = lit("MM/dd/yyyy hh:mm:ss a")
parsed = parsed.withColumn("event_ts", try_to_timestamp(trim(col("INCIDENT_DATETIME")), timestamp_format))
parsed = parsed.withColumn("event_date", to_date(col("event_ts")))
timeline_columns = (
    "INCIDENT_DATETIME", "FIRST_ASSIGNMENT_DATETIME", "FIRST_ACTIVATION_DATETIME",
    "FIRST_ON_SCENE_DATETIME", "FIRST_TO_HOSP_DATETIME", "FIRST_HOSP_ARRIVAL_DATETIME",
    "INCIDENT_CLOSE_DATETIME",
)
timeline = [
    try_to_timestamp(trim(col(name)), timestamp_format).alias(f"timeline_{index}")
    for index, name in enumerate(timeline_columns)
]
parsed = parsed.select("*", *timeline)

def seconds(source_name):
    cleaned = regexp_replace(trim(col(source_name)), ",", "")
    return when(cleaned.rlike(r"^-?\d+$"), cleaned.cast("int"))

parsed = (
    parsed.withColumn("dispatch_seconds", seconds("DISPATCH_RESPONSE_SECONDS_QY"))
    .withColumn("incident_response_seconds", seconds("INCIDENT_RESPONSE_SECONDS_QY"))
    .withColumn("travel_seconds", seconds("INCIDENT_TRAVEL_TM_SECONDS_QY"))
)

enriched = (
    parsed.withColumn(
        "dispatch_usable",
        ((trim(col("VALID_DISPATCH_RSPNS_TIME_INDC")) == lit("Y"))
         & col("dispatch_seconds").isNotNull() & (col("dispatch_seconds") >= 0)).cast("boolean"),
    )
    .withColumn(
        "incident_response_usable",
        ((trim(col("VALID_INCIDENT_RSPNS_TIME_INDC")) == lit("Y"))
         & col("incident_response_seconds").isNotNull() & (col("incident_response_seconds") >= 0)).cast("boolean"),
    )
    .withColumn(
        "travel_usable",
        (col("travel_seconds").isNotNull() & (col("travel_seconds") >= 0)).cast("boolean"),
    )
    .withColumn(
        "timestamp_order_ok",
        col("timeline_1").isNull() | col("timeline_0").isNull() | (col("timeline_1") >= col("timeline_0")),
    )
    .withColumn("incident_datetime", trim(col("INCIDENT_DATETIME")))
    .withColumn("borough", when(trim(col("BOROUGH")) == "", "UNKNOWN").otherwise(trim(col("BOROUGH"))))
    .withColumn("initial_call_type", when(trim(col("INITIAL_CALL_TYPE")) == "", "UNKNOWN").otherwise(trim(col("INITIAL_CALL_TYPE"))))
    .withColumn("final_call_type", when(trim(col("FINAL_CALL_TYPE")) == "", "UNKNOWN").otherwise(trim(col("FINAL_CALL_TYPE"))))
    .withColumn("initial_severity", when(trim(col("INITIAL_SEVERITY_LEVEL_CODE")) == "", "UNKNOWN").otherwise(trim(col("INITIAL_SEVERITY_LEVEL_CODE"))))
    .withColumn("final_severity", when(trim(col("FINAL_SEVERITY_LEVEL_CODE")) == "", "UNKNOWN").otherwise(trim(col("FINAL_SEVERITY_LEVEL_CODE"))))
    .withColumn("disposition_code", when(trim(col("INCIDENT_DISPOSITION_CODE")) == "", "UNKNOWN").otherwise(trim(col("INCIDENT_DISPOSITION_CODE"))))
    .withColumn("incident_id", trim(col("INCIDENT_ID")).cast("long"))
    .withColumn("ingested_at", current_timestamp())
    .withColumn("incident_count", lit(1))
)
for earlier, later in zip(range(1, len(timeline_columns) - 1), range(2, len(timeline_columns))):
    enriched = enriched.withColumn(
        "timestamp_order_ok",
        col("timestamp_order_ok") &
        (col(f"timeline_{later}").isNull() | col(f"timeline_{earlier}").isNull() | (col(f"timeline_{later}") >= col(f"timeline_{earlier}"))),
    )

output = enriched.select(
    "incident_id", "incident_datetime", "event_date", "borough", "initial_call_type", "final_call_type",
    "initial_severity", "final_severity", "disposition_code", "incident_count",
    "dispatch_seconds", col("VALID_DISPATCH_RSPNS_TIME_INDC").alias("dispatch_valid_flag"), "dispatch_usable",
    "incident_response_seconds", col("VALID_INCIDENT_RSPNS_TIME_INDC").alias("incident_valid_flag"),
    "incident_response_usable", "travel_seconds", "travel_usable", "timestamp_order_ok", "ingested_at",
).where(col("incident_id").isNotNull() & col("event_date").isNotNull())

kafka_output = output.select(
    col("incident_id").cast("string").alias("key"),
    to_json(struct(*[col(c) for c in output.columns])).alias("value"),
)

query = (
    kafka_output.writeStream.format("kafka")
    .option("kafka.bootstrap.servers", "kafka:9092")
    .option("topic", "ems.incidents.processed")
    .option("checkpointLocation", "/opt/ems/checkpoints/ems-incident-stream-v1")
    .outputMode("append")
    .trigger(processingTime="1 second")
    .start()
)
query.awaitTermination()
