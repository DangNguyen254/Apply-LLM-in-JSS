from ..models.jssp_model import Job, Operation, Machine, ScheduledOperation, Schedule
from ortools.sat.python import cp_model
#python -m app.services.jssp_solver

def transform_machine(machines):
    machines_dict = {machine.id: machine for machine in machines}
    return machines_dict

def transform_data(jobs: list, machines: list):
    machine_id_to_index = {machine.id: i for i, machine in enumerate(machines)}
    jobs_data = []
    for job in jobs:
        operation_list = job.operation_list
        machine_oper = [] # machine id, operation's processing time
        for operation in operation_list:
            machine_oper.append([machine_id_to_index[operation.machine_id],operation.processing_time])

        jobs_data.append(machine_oper)
    
    # jobs_data: 
    # List of jobs_data = [jobs1[[machine_oper1[machine id1 ,processing time1], [machine id2, processing time 2]], [machine_oper2]]]
    # [
    #     jobs
    #     [(0, 3), (1, 2), (2, 2)],  # Operations for J001 in order
    #     [(0, 2), (2, 1), (1, 4)],  # Operations for J002 in order
    #     [(1, 4), (2, 3)]           # Operations for J003 in order
    # ]
    # ...of tuples (operations)

    return jobs_data

def create_variable(cp, jobs_data: list, horizon: int):
    cp_variables = []

    for j_id, job in enumerate(jobs_data):
        jobs_variables = []

        for t_id, task in enumerate(job):
            name = f'J{j_id}_O{t_id}'

            start = cp.new_int_var(0, horizon, f"start_{name}")
            duration = task[1] # (machine id ,proccessing time)
            end = end_var = cp.new_int_var(0, horizon, f"end_{name}")

            interval_variable = cp.new_interval_var(start, duration, end, name)
            jobs_variables.append(interval_variable)

        cp_variables.append(jobs_variables)

    # cp_variables
    # Lists of [ [job1_op1_interval, job1_op2_interval], [job2_op1_interval, ...], ... ]
    # [
    #     job intervals
    #     [
    #         interval variables
    #         [
    #           (start,duration,end,name)
    #         ]
    #     ]
    # ]
    return cp, cp_variables

def add_precedence_constrain(cp, cp_variables):
    for job_intervals in cp_variables:
        for i in range(len(job_intervals) - 1):
            current_op = job_intervals[i]
            next_op = job_intervals[i+1]

            cp.Add(next_op.StartExpr() >= current_op.EndExpr())
    
    return cp

def add_no_overlap_constraints(cp, cp_variables, jobs_data, number_of_machines):
    machine_intervals = [[] for _ in range(number_of_machines)]

    for j_id, jobs in enumerate(jobs_data):
        for t_id, task in enumerate(jobs):
            machine_id = task[0]
            interval = cp_variables[j_id][t_id] # The operation have the exact same position throught out the jobs_data and the cp_variables

            machine_intervals[machine_id].append(interval) 
    
    for interval in machine_intervals:
        cp.AddNoOverlap(interval)

    return cp

def add_objective(cp, cp_variables, horizon):
    end_time = []

    for jobs_intervals in cp_variables:
        last_task = jobs_intervals[-1]

        end_time.append(last_task.EndExpr())


    makespan = cp.new_int_var(0, horizon, "makespan")

    cp.AddMaxEquality(makespan, end_time)
    cp.Minimize(makespan)

    return cp

def process_solution(solver, cp_variables, jobs: list[Job], machines: list[Machine], jobs_data: list):
    scheduled_operations = []
    index_to_machine_id = {i: machine.id for i, machine in enumerate(machines)}

    # Dictionaries to hold data for KPI calculations
    machine_busy_time = {machine.id: 0 for machine in machines}
    job_flow_times = {} # job_id -> (min_start, max_end)    

    for j_id, job_intervals in enumerate(cp_variables):
        for t_id, interval in enumerate(job_intervals):
            job = jobs[j_id]
            operation = job.operation_list[t_id]
            machine_index = jobs_data[j_id][t_id][0]
            machine_id = index_to_machine_id[machine_index]
            
            start_time = solver.Value(interval.StartExpr())
            end_time = solver.Value(interval.EndExpr())
            duration = end_time - start_time

            # Aggregate data for KPIs
            machine_busy_time[machine_id] += duration

            if job.id not in job_flow_times:
                job_flow_times[job.id] = [start_time, end_time]
            else:
                job_flow_times[job.id][0] = min(job_flow_times[job.id][0], start_time)
                job_flow_times[job.id][1] = max(job_flow_times[job.id][1], end_time)

            scheduled_op = ScheduledOperation(
                job_id=job.id,
                operation_id=operation.id,
                machine_id=machine_id,
                start_time=start_time,
                end_time=end_time
            )
            scheduled_operations.append(scheduled_op)

    makespan = solver.ObjectiveValue()

    # Calculate KPIs
    machine_utilization = {m_id: (busy_time / makespan) for m_id, busy_time in machine_busy_time.items()}
    total_flow_time = sum(end - start for start, end in job_flow_times.values())
    average_flow_time = total_flow_time / len(jobs) if jobs else 0

    final_schedule = Schedule(
        makespan=int(makespan),
        scheduled_operations=scheduled_operations,
        machine_utilization=machine_utilization,
        average_flow_time=average_flow_time
    )

    return final_schedule

def solver(jobs_data, jobs, machines: list):
    cp = cp_model.CpModel() 

    horizon = sum(task[1] for job in jobs_data for task in job) # Sum of all durtation
    number_of_machines = len(machines)

    cp, cp_variables = create_variable(cp, jobs_data, horizon)
    cp = add_precedence_constrain(cp, cp_variables)
    cp = add_no_overlap_constraints(cp, cp_variables, jobs_data, number_of_machines)
    cp = add_objective(cp, cp_variables, horizon)

    solver = cp_model.CpSolver()
    status = solver.Solve(cp)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        return process_solution(solver, cp_variables, jobs, machines, jobs_data)
    
    else:
        print("No solution found.")
        return None

def solve_jssp(jobs: list, machines: list):
    jobs_data = transform_data(jobs, machines)

    final_schedule = solver(jobs_data, jobs, machines)

    return final_schedule