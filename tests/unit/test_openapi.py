from app.main import app


def test_operation_ids_are_unique():
    # The frontend client gets one method per operation id, so each must be unique
    operations = [
        operation["operationId"]
        for path in app.openapi()["paths"].values()
        for operation in path.values()
    ]

    assert len(operations) == len(set(operations))
    assert "get_shipment" in operations
