from ortools.sat.python import cp_model
from ..models.jssp_model import Job, MachineGroup, ScheduledOperation, Schedule
import collections

def solve_jssp(jobs: list[Job], machine_groups: list[MachineGroup]):
    model = cp_model.CpModel()
    
    machine_group_map = {mg.id: mg for mg in machine_groups}
    all_machine_instances = [f"{group.id}_{i}" for group in machine_groups for i in range(group.quantity)]
    if not all_machine_instances:
        return None # Cannot solve if there are no machines

    horizon = sum(op.processing_time for job in jobs for op in job.operation_list)
    intervals_per_machine_instance = collections.defaultdict(list)
    task_to_op_map = {}

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

            
            # Use the presence variables directly for the constraint
            presence_vars = [p for i, p in optional_intervals_with_presence]
            model.AddExactlyOne(presence_vars)

            # Store the list of tuples in the map
            task_to_op_map[(job.id, op.id)] = optional_intervals_with_presence
    
    # Constraints
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

    for instance_id in all_machine_instances:
        model.AddNoOverlap(intervals_per_machine_instance[instance_id])

    makespan = model.NewIntVar(0, horizon, 'makespan')
    all_end_times = []
    for job in jobs:
        if not job.operation_list:
            continue
        last_op = job.operation_list[-1]
        last_op_intervals = task_to_op_map[(job.id, last_op.id)]
        job_end_time = model.NewIntVar(0, horizon, f'end_{job.id}')
        model.AddMaxEquality(job_end_time, [interval.EndExpr() for interval, presence_var in last_op_intervals])
        all_end_times.append(job_end_time)
    
    if not all_end_times:
        model.Add(makespan == 0)
    else:
        model.AddMaxEquality(makespan, all_end_times)

    model.Minimize(makespan)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        scheduled_ops = []
        machine_busy_time = collections.defaultdict(int)
        job_flow_times = {}

        for job in jobs:
            for op in job.operation_list:
                for i, (interval, presence_var) in enumerate(task_to_op_map[(job.id, op.id)]):
                    # Check the value of the presence variable directly
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

        final_makespan = solver.ObjectiveValue()
        machine_utilization = {inst_id: (busy_time / final_makespan) if final_makespan > 0 else 0 for inst_id, busy_time in machine_busy_time.items()}
        total_flow_time = sum(end - start for start, end in job_flow_times.values())
        average_flow_time = total_flow_time / len(jobs) if jobs else 0
        
        return Schedule(makespan=int(final_makespan), scheduled_operations=scheduled_ops, machine_utilization=machine_utilization, average_flow_time=average_flow_time)
    return None