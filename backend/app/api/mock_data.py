"""
This file contains the "Live Data" definition for the automotive plant.
It is imported by 'database.py' only during the initial database 
population (or after a developer reset).

This data is designed to specifically test two business use cases:
1.  BUC-1 (Equipment Breakdown): "Body-Shop-Welding" (MG-WELD) has a
    quantity of 4, allowing for a simulation where it's reduced to 3.
2.  BUC-2 (Rush Order): "Priority-Fleet-01" (JOB-F001) exists with a
    low priority (2), while another job "PART-RPL" (JOB-P401) has the
    current highest priority (8). The LLM must be able to find both
    and correctly set the new priority to 9.
"""

TEST_PROBLEMS = {
    "automotive_plant_live": {
        # --- MACHINE GROUPS (DEPARTMENTS) ---
        "machines": [
            {
                "id": "MG-STAMP",
                "name": "Stamping Presses",
                "quantity": 2
            },
            {
                "id": "MG-WELD",
                "name": "Body-Shop-Welding",
                "quantity": 4  # Critical for BUC-1
            },
            {
                "id": "MG-PAINT",
                "name": "Paint Booths",
                "quantity": 3
            },
            {
                "id": "MG-ASSY",
                "name": "General Assembly Lines",
                "quantity": 2
            }
        ],
        
        # --- JOBS (PRODUCTION ORDERS) ---
        "jobs": [
            # Job 1: BUC-2 Regular Customer "CUST-304"
            {
                "id": "JOB-C304",
                "name": "CUST-304 (Std. Sedan)",
                "priority": 5, # Normal priority
                "operation_list": [
                    {
                        "id": "JOB-C304-OP1",
                        "machine_group_id": "MG-STAMP",
                        "processing_time": 2,
                        "predecessors": []
                    },
                    {
                        "id": "JOB-C304-OP2",
                        "machine_group_id": "MG-WELD",
                        "processing_time": 5,
                        "predecessors": ["JOB-C304-OP1"]
                    },
                    {
                        "id": "JOB-C304-OP3",
                        "machine_group_id": "MG-PAINT",
                        "processing_time": 8,
                        "predecessors": ["JOB-C304-OP2"]
                    },
                    {
                        "id": "JOB-C304-OP4",
                        "machine_group_id": "MG-ASSY",
                        "processing_time": 4,
                        "predecessors": ["JOB-C304-OP3"]
                    }
                ]
            },
            # Job 2: Another regular job
            {
                "id": "JOB-C305",
                "name": "CUST-305 (Std. SUV)",
                "priority": 5, # Normal priority
                "operation_list": [
                    {
                        "id": "JOB-C305-OP1",
                        "machine_group_id": "MG-STAMP",
                        "processing_time": 3,
                        "predecessors": []
                    },
                    {
                        "id": "JOB-C305-OP2",
                        "machine_group_id": "MG-WELD",
                        "processing_time": 6,
                        "predecessors": ["JOB-C305-OP1"]
                    },
                    {
                        "id": "JOB-C305-OP3",
                        "machine_group_id": "MG-PAINT",
                        "processing_time": 9,
                        "predecessors": ["JOB-C305-OP2"]
                    },
                    {
                        "id": "JOB-C305-OP4",
                        "machine_group_id": "MG-ASSY",
                        "processing_time": 5,
                        "predecessors": ["JOB-C305-OP3"]
                    }
                ]
            },
            # Job 3: BUC-2 Current Highest Priority Job
            {
                "id": "JOB-P401",
                "name": "PART-RPL (Spare Door)",
                "priority": 8, # Current highest priority
                "operation_list": [
                    {
                        "id": "JOB-P401-OP1",
                        "machine_group_id": "MG-STAMP",
                        "processing_time": 1,
                        "predecessors": []
                    },
                    {
                        "id": "JOB-P401-OP2",
                        "machine_group_id": "MG-PAINT",
                        "processing_time": 3,
                        "predecessors": ["JOB-P401-OP1"]
                    }
                ]
            },
            # Job 4: BUC-2 Rush Order Job (low priority to start)
            {
                "id": "JOB-F001",
                "name": "Priority-Fleet-01 (Ambulance)",
                "priority": 2, # Starts with low priority
                "operation_list": [
                    {
                        "id": "JOB-F001-OP1",
                        "machine_group_id": "MG-STAMP",
                        "processing_time": 3,
                        "predecessors": []
                    },
                    {
                        "id": "JOB-F001-OP2",
                        "machine_group_id": "MG-WELD",
                        "processing_time": 7,
                        "predecessors": ["JOB-F001-OP1"]
                    },
                    {
                        "id": "JOB-F001-OP3",
                        "machine_group_id": "MG-PAINT",
                        "processing_time": 10,
                        "predecessors": ["JOB-F001-OP2"]
                    },
                    {
                        "id": "JOB-F001-OP4",
                        "machine_group_id": "MG-ASSY",
                        "processing_time": 6,
                        "predecessors": ["JOB-F001-OP3"]
                    }
                ]
            }
        ]
    }
}