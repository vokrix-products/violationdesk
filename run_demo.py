import json

import processor


def main():
    test_bytes = b"""received_timestamp,received_via,complainant_name,complainant_email,complainant_phone,association,property_address,unit_number,violation_category,violation_description,photo_evidence,incident_date,reporter_type,status,due_date
2025-04-01T08:30:00,email,Alice Smith,alice@example.com,555-0100,Oakwood HOA,123 Oak Lane,4B,Lawn,Grass over 8 inches,2,2025-03-28,resident,New,2025-04-15
"""

    results = processor.process_file(test_bytes)

    assert isinstance(results, list)
    assert len(results) == 1

    record = results[0]
    assert record["title"] == "123 Oak Lane Unit 4B"
    assert record["status"] == "New"
    assert record["due_date"] == "2025-04-15"
    assert "due_date" not in record["details"]
    assert record["details"]["Violation category"] == "Lawn"

    print("Demo ran successfully")
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
