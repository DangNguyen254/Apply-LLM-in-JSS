class Job:
    def __init__(self, id, name, operation_list, priority):
        self.id = id
        self.name = name
        self.operation_list = operation_list
        self.priority = priority

class Operation:
    def __init__(self, id, name, machine_need, duration):
        self.id = id
        self.name = name
        self.machine_need = machine_need
        self.duration = duration

class Machine:
    def __init__(self, id, name):
        self.id = id
        self.name = name

class ScheduledOperation:
    def __init__(self, id, job_belong, machine_assigned, time_start, time_end):
        self.id = id
        self.job_belong = job_belong
        self.machine_assigned = machine_assigned
        self.time_start = time_start
        self.time_end = time_end

class Schedule:
    def __init__(self, id, scheduled_op_list):
        self.id = id
        self.scheduled_op_list = scheduled_op_list

        

