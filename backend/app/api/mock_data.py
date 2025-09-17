# ==============================================================================
# Problem 1: Small Machine Shop
# ==============================================================================
problem_1 = {
    "name": "Small Machine Shop",
    "machines": [
        {"id": "M1", "name": "Milling Machine M1", "availability": True},
        {"id": "L1", "name": "Lathe Machine L1", "availability": True},
        {"id": "D1", "name": "Drilling Press D1", "availability": True},
    ],
    "jobs": [
        {
            "id": "J101", "name": "Component Alpha", "priority": 1,
            "operation_list": [
                {"id": "J101_O1", "machine_id": "M1", "processing_time": 5, "predecessors": []},
                {"id": "J101_O2", "machine_id": "L1", "processing_time": 4, "predecessors": ["J101_O1"]},
                {"id": "J101_O3", "machine_id": "D1", "processing_time": 6, "predecessors": ["J101_O2"]},
            ]
        },
        {
            "id": "J102", "name": "Component Beta", "priority": 2,
            "operation_list": [
                {"id": "J102_O1", "machine_id": "L1", "processing_time": 3, "predecessors": []},
                {"id": "J102_O2", "machine_id": "M1", "processing_time": 7, "predecessors": ["J102_O1"]},
            ]
        },
        {
            "id": "J103", "name": "Component Gamma", "priority": 1,
            "operation_list": [
                {"id": "J103_O1", "machine_id": "D1", "processing_time": 4, "predecessors": []},
                {"id": "J103_O2", "machine_id": "M1", "processing_time": 4, "predecessors": ["J103_O1"]},
                {"id": "J103_O3", "machine_id": "L1", "processing_time": 5, "predecessors": ["J103_O2"]},
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
        {"id": "C1", "name": "Cutter C1", "availability": True},
        {"id": "W1", "name": "Welder W1", "availability": True},
        {"id": "P1", "name": "Painter P1", "availability": False},
        {"id": "A1", "name": "Assembler A1", "availability": True},
    ],
    "jobs": [
        {
            "id": "J201", "name": "Frame Assembly", "priority": 3,
            "operation_list": [
                {"id": "J201_O1", "machine_id": "C1", "processing_time": 3, "predecessors": []},
                {"id": "J201_O2", "machine_id": "W1", "processing_time": 5, "predecessors": ["J201_O1"]},
                {"id": "J201_O3", "machine_id": "A1", "processing_time": 4, "predecessors": ["J201_O2"]},
            ]
        },
        {
            "id": "J202", "name": "Panel Preparation", "priority": 2,
            "operation_list": [
                {"id": "J202_O1", "machine_id": "C1", "processing_time": 4, "predecessors": []},
                {"id": "J202_O2", "machine_id": "P1", "processing_time": 6, "predecessors": ["J202_O1"]},
            ]
        },
        {
            "id": "J203", "name": "Finishing Touches", "priority": 1,
            "operation_list": [
                {"id": "J203_O1", "machine_id": "W1", "processing_time": 2, "predecessors": []},
                {"id": "J203_O2", "machine_id": "A1", "processing_time": 6, "predecessors": ["J203_O1"]},
            ]
        }
    ]
}

TEST_PROBLEMS = {
    "problem_1": problem_1,
    "problem_2": problem_2,
}