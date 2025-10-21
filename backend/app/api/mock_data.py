# ==============================================================================
# Problem 1: Small Machine Shop
# ==============================================================================
problem_1 = {
    "name": "Small Machine Shop",
    "machines": [
        {"id": "M001", "name": "Milling Machine", "availability": True},
        {"id": "M002", "name": "Lathe Machine", "availability": True},
        {"id": "M003", "name": "Drilling Press", "availability": True},
    ],
    "jobs": [
        {
            "id": "J001", "name": "Component Alpha", "priority": 1,
            "operation_list": [
                {"id": "J001-OP01", "machine_id": "M001", "processing_time": 5, "predecessors": []},
                {"id": "J001-OP02", "machine_id": "M002", "processing_time": 4, "predecessors": ["J001-OP01"]},
                {"id": "J001-OP03", "machine_id": "M003", "processing_time": 6, "predecessors": ["J001-OP02"]},
            ]
        },
        {
            "id": "J002", "name": "Component Beta", "priority": 2,
            "operation_list": [
                {"id": "J002-OP01", "machine_id": "M002", "processing_time": 3, "predecessors": []},
                {"id": "J002-OP02", "machine_id": "M001", "processing_time": 7, "predecessors": ["J002-OP01"]},
            ]
        },
        {
            "id": "J003", "name": "Component Gamma", "priority": 1,
            "operation_list": [
                {"id": "J003-OP01", "machine_id": "M003", "processing_time": 4, "predecessors": []},
                {"id": "J003-OP02", "machine_id": "M001", "processing_time": 4, "predecessors": ["J003-OP01"]},
                {"id": "J003-OP03", "machine_id": "M002", "processing_time": 5, "predecessors": ["J003-OP02"]},
            ]
        }
    ]
}

# ==============================================================================
# Problem 2: Complex Production Line
# ==============================================================================
problem_2 = {
    "name": "Complex Production Line",
    "machines": [
        {"id": "M001", "name": "Cutter", "availability": True},
        {"id": "M002", "name": "Welder", "availability": True},
        {"id": "M003", "name": "Painter", "availability": False},
        {"id": "M004", "name": "Assembler", "availability": True},
    ],
    "jobs": [
        {
            "id": "J001", "name": "Frame Assembly", "priority": 3,
            "operation_list": [
                {"id": "J001-OP01", "machine_id": "M001", "processing_time": 3, "predecessors": []},
                {"id": "J001-OP02", "machine_id": "M002", "processing_time": 5, "predecessors": ["J001-OP01"]},
                {"id": "J001-OP03", "machine_id": "M004", "processing_time": 4, "predecessors": ["J001-OP02"]},
            ]
        },
        {
            "id": "J002", "name": "Panel Preparation", "priority": 2,
            "operation_list": [
                {"id": "J002-OP01", "machine_id": "M001", "processing_time": 4, "predecessors": []},
                {"id": "J002-OP02", "machine_id": "M003", "processing_time": 6, "predecessors": ["J002-OP01"]},
            ]
        },
        {
            "id": "J003", "name": "Finishing Touches", "priority": 1,
            "operation_list": [
                {"id": "J003-OP01", "machine_id": "M002", "processing_time": 2, "predecessors": []},
                {"id": "J003-OP02", "machine_id": "M004", "processing_time": 6, "predecessors": ["J003-OP01"]},
            ]
        }
    ]
}

TEST_PROBLEMS = {
    "problem_1": problem_1,
    "problem_2": problem_2,
}