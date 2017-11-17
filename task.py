from common import tile_is_solid
from astar import astar
from breadth import find_path_to_matching

# A Task is a unitary action that a unit should take.
# Once a task is complete, it can run code to decide what
# next action should be taken.  This code is given as
# a callback.
class TaskGo(object):
    """
    The target location must be reachable by the unit.

    Arguments:
        stage:         the Stage containing the unit
        unit:          the unit (e.g., Penguin) whose task this
        target:        the target position as a pair of x-y coordinates
        blocked_proc:  the procedure to run if the path is broken
        finished_proc: the procedure to run if the task is finished
    """
    def __init__(self, stage, unit, target,
                 blocked_proc, finished_proc):
        self._unit = unit
        self._target = target
        self._target_is_solid = \
          tile_is_solid(stage.get_tile_at(target[0], target[1]))
        self._blocked_proc = blocked_proc
        self._finished_proc = finished_proc
        self._stage = stage

        # If the unit is already at its goal, just finish the task.
        if (unit.x, unit.y) == target:
            self._finished_proc()
            return

        assert self._target_is_reachable(), \
               'destination tile is unreachable'

        # Find the path to the destination.
        self._path = astar(stage, (unit.x, unit.y), target)

    def _target_is_reachable(self):
        tx, ty = self._target
        return self._unit.partition[ty][tx]

    def enact(self):
        # bug - if we are after an object and the object becomes
        #       unreachable, that should count as a block!
        # If the target is not reachable, call blocked_proc.
        if not self._target_is_reachable():
            self._blocked_proc()
            return

        unit = self._unit
        x, y = unit.x, unit.y
        path = self._path

        if len(path) == 0:
            # We have reached the goal, so finish the task.
            self._finished_proc()
            return
        elif self._target_is_solid and len(path) == 1:
            # The target is solid and we've reached it,
            # so finish the task.
            self._finished_proc()
            return

        dx, dy = (self._path[0][0] - x, self._path[0][1] - y)
        assert -1 <= dx <= 1
        assert -1 <= dy <= 1

        if not tile_is_solid(self._stage.get_tile_at(x + dx, y + dy)):
            # Step toward the target.
            unit.x += dx
            unit.y += dy
            self._path = path[1:]
        else:
            # The path was blocked, so calculate a new path.
            self._path = astar(self._stage,
                               (unit.x, unit.y),
                               self._target)

class TaskMine(object):
    """
    Arguments:
        stage:         the Stage containing the unit
        unit:          the unit (e.g., Penguin) whose task this
        target:        the target position as a pair of x-y coordinates
        finished_proc: the procedure to run if the task is finished
    """
    def __init__(self, stage, unit, target, finished_proc):
        self._stage = stage
        self._unit = unit
        self._target = target
        self._work_left = 10
        self._assert_unit_is_within_range()
        self._finished_proc = finished_proc

    def _assert_unit_is_within_range(self):
        x, y = self._unit.x, self._unit.y
        tx, ty = self._target

        assert -1 <= x - tx <= 1, 'not in range of mine job'
        assert -1 <= y - ty <= 1, 'not in range of mine job'

    def enact(self):
        self._assert_unit_is_within_range()
        tx, ty = self._target

        self._work_left -= 1
        if self._work_left == 0:
            self._stage.set_tile_at(tx, ty, 1)
            self._finished_proc()
            return

class TaskTake(object):
    def __init__(self, stage, unit, entity, finished_proc):
        self._stage = stage
        self._unit = unit
        self._entity = entity
        self._finished_proc = finished_proc
        assert (unit.x, unit.y) == entity.location

    def enact(self):
        assert not self._unit._held_entity, \
               'unit tried to take when its hands were full'
        self._unit._held_entity = self._entity
        self._entity.relinquish()
        self._entity.location = None
        self._stage.delete_entity(self._entity)
        self._finished_proc()
        return

class TaskDrop(object):
    def __init__(self, stage, unit, finished_proc):
        self._stage = stage
        self._unit = unit
        self._finished_proc = finished_proc

    def enact(self):
        unit = self._unit
        entity = unit._held_entity
        unit._held_entity = None

        self._stage.add_entity(entity, (unit.x, unit.y))
        entity.location = (unit.x, unit.y)
        self._finished_proc()
        return

class TaskGoToAnyMatchingSpot(object):
    """
    Go to the nearest spot that matches some condition.

    This tasks searches breadth-first, so only use it for conditions
    which will probably result in short searches, e.g., finding an
    empty tile.

    Arguments:
        stage:         the Stage containing the unit
        unit:          the unit (e.g., Penguin) whose task this
        condition_func: the function returning whether the spot is okay
        impossible_proc: the procedure to run if there is no empty spot
        finished_proc: the procedure to run if the task is finished
    """
    def __init__(self, stage, unit, condition_func,
                 impossible_proc, finished_proc):
        self._unit = unit
        self._condition_func = condition_func
        self._impossible_proc = impossible_proc
        self._finished_proc = finished_proc
        self._stage = stage
        self._recalculate()

    def _recalculate(self):
        stage = self._stage
        unit = self._unit

        self._path = find_path_to_matching(stage,
                                           (unit.x, unit.y),
                                           self._condition_func)

        # If the unit has no path, run the impossible proc and quit.
        if self._path is None:
            self._impossible_proc()
            return

        self._target = self._path[-1]
        assert self._target_is_reachable(), \
               'destination tile is unreachable'

        # If the unit is already at its goal, just finish the task.
        if (unit.x, unit.y) == self._target:
            self._finished_proc()
            return

        target = self._target
        self._target_is_solid = \
          tile_is_solid(stage.get_tile_at(target[0], target[1]))

    def _target_is_reachable(self):
        tx, ty = self._target
        return self._unit.partition[ty][tx]

    def enact(self):
        # bug - if we are after an object and the object becomes
        #       unreachable, that should count as a block!
        # If the target is not reachable, call blocked_proc.
        if not self._target_is_reachable():
            self._recalculate()

            if self._path is None:
                return

        unit = self._unit
        x, y = unit.x, unit.y
        path = self._path

        if len(path) == 0:
            # bug - will checking this here cause penguins to
            #       delay for a turn, since the move happened
            #       on the last turn?
            # We have reached the goal, so finish the task.
            self._finished_proc()
            return
        elif self._target_is_solid and len(path) == 1:
            # The target is solid and we've reached it,
            # so finish the task.
            self._finished_proc()
            return

        dx, dy = (self._path[0][0] - x, self._path[0][1] - y)
        assert -1 <= dx <= 1
        assert -1 <= dy <= 1

        if not tile_is_solid(self._stage.get_tile_at(x + dx, y + dy)):
            # Step toward the target.
            unit.x += dx
            unit.y += dy
            self._path = path[1:]
        else:
            # The path was blocked, so calculate a new path.
            self._path = astar(self._stage,
                               (unit.x, unit.y),
                               self._target)
class TaskTrade(object):
    def __init__(self, stage, unit, entity, finished_proc):
        self._stage = stage
        self._unit = unit
        self._entity = entity
        self._finished_proc = finished_proc

    def enact(self):
        unit = self._unit

        held = unit._held_entity
        grounded = self._stage.entity_at((unit.x, unit.y))

        assert (unit.x, unit.y) == grounded.location
        assert held is not None
        assert grounded is not None

        # Remove the object on the ground.
        grounded.relinquish()
        grounded.location = None
        self._stage.delete_entity(grounded)

        # Place the unit's object onto the ground.
        self._stage.add_entity(held, (unit.x, unit.y))
        held.location = (unit.x, unit.y)

        # Give the removed object to the unit.
        self._unit._held_entity = grounded

        self._finished_proc()
        return
