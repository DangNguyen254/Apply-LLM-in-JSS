from ortools.sat.python import cp_model
from ..models.jssp_model import Job, MachineGroup, ScheduledOperation, Schedule
import collections

def solve_jssp(jobs: list[Job], machine_groups: list[MachineGroup]):
    model = cp_model.CpModel()
    
    machine_group_map = {mg.id: mg for mg in machine_groups}
    all_machine_instances = [f"{group.id}_{i}" for group in machine_groups for i in range(group.quantity)]
    if not all_machine_instances:
        return None # Cannot solve if there are no machines

    # Calculate horizon (a "safe" upper bound for all time)
    horizon = sum(op.processing_time for job in jobs for op in job.operation_list)

    # --- Data Structures ---
    # (This section is unchanged)
    intervals_per_machine_instance = collections.defaultdict(list)
    # This map stores: (job_id, op_id) -> list of (interval_var, presence_var)
    task_to_op_map = {} 

    # --- Create Interval Variables ---
    # (This section is unchanged)
    for job in jobs:
        for op in job.operation_list:
            if op.machine_group_id not in machine_group_map:
                return None
            group = machine_group_map[op.machine_group_id]
            optional_intervals_with_presence = []
            for i in range(group.quantity):
                instance_id = f"{group.id}_{i}"
                suffix = f'_{job.id}_{op.id}_on_{instance_id}'
                start_var = model.NewIntVar(0, horizon, 'start' + suffix)
                end_var = model.NewIntVar(0, horizon, 'end' + suffix)

                presence_var = model.NewBoolVar('presence' + suffix)
                interval = model.NewOptionalIntervalVar(start_var, op.processing_time, end_var, presence_var, 'interval' + suffix)
                intervals_per_machine_instance[instance_id].append(interval)
                optional_intervals_with_presence.append((interval, presence_var))

            presence_vars = [p for i, p in optional_intervals_with_presence]
            model.AddExactlyOne(presence_vars)
            task_to_op_map[(job.id, op.id)] = optional_intervals_with_presence
    
    # --- Add Precedence Constraints ---
    # (This section is unchanged)
    for job in jobs:
        op_map = {op.id: op for op in job.operation_list}
        for op in job.operation_list:
            if op.predecessors:
                for pred_op_id in op.predecessors:
                    if pred_op_id in op_map:
                        pred_intervals = task_to_op_map[(job.id, pred_op_id)]
                        current_intervals = task_to_op_map[(job.id, op.id)]
                        
                        pred_end_time = model.NewIntVar(0, horizon, f'end_{pred_op_id}')
                        model.AddMaxEquality(pred_end_time, [interval.EndExpr() for interval, presence_var in pred_intervals])
                        
                        current_start_time = model.NewIntVar(0, horizon, f'start_{op.id}')
                        model.AddMinEquality(current_start_time, [interval.StartExpr() for interval, presence_var in current_intervals])

                        model.Add(current_start_time >= pred_end_time)

    # --- Add No-Overlap Constraints ---
    # (This section is unchanged)
    for instance_id in all_machine_instances:
        model.AddNoOverlap(intervals_per_machine_instance[instance_id])

    # --- NEW: Multi-Objective Function (Makespan + Priority) ---
    
    # 1. Define Makespan variable (Secondary Objective)
    makespan = model.NewIntVar(0, horizon, 'makespan')
    all_end_times = []
    
    # 2. Define Weighted Completion Time variables (Primary Objective)
    # This will hold the list of (job_end_time * job_priority)
    weighted_completion_terms = []
    
    # We use horizon as a large weight to make priority more important
    # Any 1-unit improvement in priority score is worth `horizon` units of makespan
    # This forces the solver to optimize for priority FIRST.
    PRIMARY_WEIGHT = horizon + 1 
    SECONDARY_WEIGHT = 1

    max_priority = sum(j.priority for j in jobs) if jobs else 1
    
    for job in jobs:
        if not job.operation_list:
            continue
            
        # Find the end time of the *last* operation of this job
        last_op = job.operation_list[-1]
        last_op_intervals = task_to_op_map[(job.id, last_op.id)]
        job_end_time = model.NewIntVar(0, horizon, f'end_{job.id}')
        model.AddMaxEquality(job_end_time, [interval.EndExpr() for interval, presence_var in last_op_intervals])
        
        # This is for the secondary objective (makespan)
        all_end_times.append(job_end_time)
        
        # This is for the primary objective (priority)
        # We assume HIGHER number = HIGHER priority
        # We multiply the job's end time by its priority.
        # The solver will be heavily penalized for letting a high-priority job finish late.
        weighted_term = model.NewIntVar(0, horizon * max(1, job.priority), f'weighted_end_{job.id}')
        model.Add(weighted_term == job_end_time * job.priority)
        weighted_completion_terms.append(weighted_term)

    # Set up the secondary objective (makespan)
    if not all_end_times:
        model.Add(makespan == 0)
    else:
        model.AddMaxEquality(makespan, all_end_times)

    # Set up the primary objective (total weighted completion)
    total_weighted_completion = model.NewIntVar(0, horizon * horizon * max(1, max_priority), 'total_weighted_completion')
    model.Add(total_weighted_completion == sum(weighted_completion_terms))

    # 3. Create the final combined objective function
    # We multiply the primary objective by a huge weight.
    combined_objective_var = model.NewIntVar(0, (horizon * horizon * horizon * max(1, max_priority)) + horizon, 'combined_objective')
    model.Add(combined_objective_var == (PRIMARY_WEIGHT * total_weighted_completion) + (SECONDARY_WEIGHT * makespan))

    # 4. Set the model to minimize this new combined objective
    model.Minimize(combined_objective_var)

    # --- Solve ---
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    # --- Process Results ---
    # (This section is unchanged. It still calculates the correct KPIs
    # based on the solution the solver found.)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        scheduled_ops = []
        machine_busy_time = collections.defaultdict(int)
        job_flow_times = {}

        for job in jobs:
            for op in job.operation_list:
                for i, (interval, presence_var) in enumerate(task_to_op_map[(job.id, op.id)]):
                    if solver.Value(presence_var):
                        instance_id = f"{op.machine_group_id}_{i}"
                        start_time = solver.Value(interval.StartExpr())
                        end_time = solver.Value(interval.EndExpr())

                        scheduled_ops.append(ScheduledOperation(job_id=job.id, operation_id=op.id, machine_instance_id=instance_id, start_time=start_time, end_time=end_time))

                        machine_busy_time[instance_id] += (end_time - start_time)
                        if job.id not in job_flow_times:
                            job_flow_times[job.id] = [start_time, end_time]
                        else:
                            job_flow_times[job.id][0] = min(job_flow_times[job.id][0], start_time)
                            job_flow_times[job.id][1] = max(job_flow_times[job.id][1], end_time)
                        break

        # We get the makespan value from its variable, not the objective value
        final_makespan = solver.Value(makespan)
        machine_utilization = {inst_id: (busy_time / final_makespan) if final_makespan > 0 else 0 for inst_id, busy_time in machine_busy_time.items()}
        total_flow_time = sum(end - start for start, end in job_flow_times.values())
        average_flow_time = total_flow_time / len(jobs) if jobs else 0
        
        return Schedule(makespan=int(final_makespan), scheduled_operations=scheduled_ops, machine_utilization=machine_utilization, average_flow_time=average_flow_time)
    
    return None