problem_1 = {
    "name": "Machine Shop with Resource Pools",
    "machines": [
        {"id": "MG001", "name": "Milling Machine", "quantity": 2},
        {"id": "MG002", "name": "Lathe Machine", "quantity": 1},
        {"id": "MG003", "name": "Drilling Press", "quantity": 2},
    ],
    "jobs": [
        {
            "id": "J001", "name": "Component Alpha", "priority": 1,
            "operation_list": [
                {"id": "J001-OP01", "machine_group_id": "MG001", "processing_time": 5, "predecessors": []},
                {"id": "J001-OP02", "machine_group_id": "MG002", "processing_time": 4, "predecessors": ["J001-OP01"]},
                {"id": "J001-OP03", "machine_group_id": "MG003", "processing_time": 6, "predecessors": ["J001-OP02"]},
            ]
        },
        {
            "id": "J002", "name": "Component Beta", "priority": 2,
            "operation_list": [
                {"id": "J002-OP01", "machine_group_id": "MG002", "processing_time": 3, "predecessors": []},
                {"id": "J002-OP02", "machine_group_id": "MG001", "processing_time": 7, "predecessors": ["J002-OP01"]},
            ]
        },
        {
            "id": "J003", "name": "Component Gamma", "priority": 1,
            "operation_list": [
                {"id": "J003-OP01", "machine_group_id": "MG003", "processing_time": 4, "predecessors": []},
                {"id": "J003-OP02", "machine_group_id": "MG001", "processing_time": 4, "predecessors": ["J003-OP01"]},
                {"id": "J003-OP03", "machine_group_id": "MG002", "processing_time": 5, "predecessors": ["J003-OP02"]},
            ]
        }
    ]
}
TEST_PROBLEMS = { "problem_1": problem_1 }