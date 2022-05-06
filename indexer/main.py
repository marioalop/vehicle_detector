from kafka import KafkaConsumer, KafkaProducer
import os
import json
from schemas import Vehicle


KAFKA_BROKER_URL = os.environ.get("KAFKA_BROKER_URL")
DETECTIONS_TOPIC = os.environ.get("DETECTIONS_TOPIC")
ALERTS_TOPIC = os.environ.get("ALERTS_TOPIC")
SUSPICIOUS_VEHICLE = os.environ.get("SUSPICIOUS_VEHICLE")


class KafkaConnector:
    def __init__(self, topic):
        self._consumer = KafkaConsumer(topic,
                                       bootstrap_servers=KAFKA_BROKER_URL,
                                       value_deserializer=lambda x: json.loads(x.decode())
                                       )
        self.producer = KafkaProducer(
                            bootstrap_servers=KAFKA_BROKER_URL,
                            # Encode all values as JSON
                            value_serializer=lambda value: json.dumps(value).encode(),
                        )
    
    @property
    def consumer(self):
        return self._consumer

    @consumer.setter
    def consumer(self, value):
        if isinstance(value, KafkaConsumer):
            self._consumer = value

    def receive_message(self):
        for message in self._consumer:
            data = message.value
            vehicle = Vehicle(**data)
            vehicle.save()
            if vehicle.category == SUSPICIOUS_VEHICLE:
                self.producer.send(ALERTS_TOPIC, value=vehicle.serialize())


if __name__ == '__main__':
    conn = KafkaConnector(DETECTIONS_TOPIC)
    conn.receive_message()
