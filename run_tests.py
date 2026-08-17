import processor


def test_csv():
    test_bytes = b"""received_timestamp,received_via,complainant_name,complainant_email,complainant_phone,association,property_address,unit_number,violation_category,violation_description,photo_evidence,incident_date,reporter_type,status,due_date
2025-04-01T08:30:00,email,Alice Smith,alice@example.com,555-0100,Oakwood HOA,123 Oak Lane,4B,Lawn,Grass over 8 inches,2,2025-03-28,resident,New,2025-04-15
"""
    records = processor.process_file(test_bytes)

    assert isinstance(records, list)
    assert len(records) == 1

    record = records[0]
    assert record["title"] == "123 Oak Lane Unit 4B"
    assert record["status"] == "New"
    assert record["due_date"] == "2025-04-15"
    assert "due_date" not in record["details"]
    assert record["details"]["Violation category"] == "Lawn"


def test_text_fallback():
    text_bytes = b"Property address: 45 Maple Court Unit 7A\nViolation description: Broken fence\nDue date: 2025-04-30"
    records = processor.process_file(text_bytes)

    assert isinstance(records, list)
    assert len(records) == 1
    assert records[0]["title"] == "45 Maple Court Unit 7A"
    assert records[0]["due_date"] == "2025-04-30"
    assert "due_date" not in records[0]["details"]


test_csv()
test_text_fallback()
print("All tests passed")
