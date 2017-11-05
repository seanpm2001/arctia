from config import *
from common import *

class JobSearch(object):
    """
    A JobSearch searches the map for untaken jobs that Penguins can do.

    This class exists because the seeking algorithm uses two big arrays
    which should not be reallocated every time the seek runs.
    """
    LEFT      = 0
    UPLEFT    = 1
    UPRIGHT   = 2
    RIGHT     = 3
    UP        = 4
    DOWN      = 5
    DOWNLEFT  = 6
    DOWNRIGHT = 7

    def __init__(self, stage, mine_jobs, timeslice, stopwatch):
        """
        Create a new JobSearch.

        Arguments:
            stage: the stage
            mine_jobs: the list of active Jobs
            timeslice: which timeslice the JobSearch activates in
            stopwatch: the global Stopwatch

        Returns:
            the new JobSearch
        """
        assert timeslice >= 0 and timeslice < NUM_OF_TIMESLICES

        self.busy = False
        self._stage = stage
        self._mine_jobs = mine_jobs

        self._paths = [[None for x in range(self._stage.width)]
                       for y in range(self._stage.height)]
        self._visited = [[False for x in range(self._stage.width)]
                         for y in range(self._stage.height)]
        self._staleness = [[False for x in range(self._stage.width)]
                           for y in range(self._stage.height)]
        self._offsets = [( 0, -1),
                         ( 0, 1),
                         (-1, 0),
                         ( 1, 0),
                         (-1, -1),
                         (-1, 1),
                         ( 1, -1),
                         ( 1, 1)]
        self._directions = [JobSearch.UP,
                            JobSearch.DOWN,
                            JobSearch.LEFT,
                            JobSearch.RIGHT,
                            JobSearch.UPLEFT,
                            JobSearch.DOWNLEFT,
                            JobSearch.UPRIGHT,
                            JobSearch.DOWNRIGHT]
        self._timeslice = timeslice
        self._stopwatch = stopwatch
        self._cookie = stopwatch.start()

    def start(self, from_x, from_y):
        """
        Begin searching for jobs starting from the given position.

        Arguments:
            from_x: the initial x coordinate
            from_y: the initial y coordinate

        Returns:
            the found job as (x, y) or None if no job was found
        """
        self._shortest_path = []
        self._start_x = from_x
        self._start_y = from_y

        # Clear the state arrays.
        for y in range(len(self._visited)):
            for x in range(len(self._visited[0])):
                self._visited[y][x] = False
                self._staleness[y][x] = False
                self._paths[y][x] = None

        # Mark the starting point as visited.
        self._visited[from_y][from_x] = True

        # State that the job searcher is busy.
        self.busy = True

    def notify(self, xoff, yoff):
        """
        Notify the job search that the originating mob has moved.

        Job searches are always started from some mob's location.
        Because job searches are run incrementally over many frames,
        the object which started the job search might move in mid-search.

        In order for the job search to give a correct shortest path
        to the found job, it needs to know where the originating mob
        is at all times.  To that end, this procedure should be run
        whenever the mob responsible for the job search moves.

        For example, if a penguin moves (1, 1) from its previous
        position, it should also run notify(1, 1) on its job_search.

        Arguments:
            xoff: the offset from the original starting x coordinate
            yoff: the offset from the original starting y coordinate
        """
        if not self.busy:
            return

        self._shortest_path.insert(0, (-xoff, -yoff))

    def _traceback(self, job):
        """
        Return the already-calculated shortest path to the found Job.

        Arguments:
            job:
                The Job we found.

        Returns:
            A list of 2-tuples representing steps along the path to
            the Job.  For example, [(1, 1), (1, 0), ...]
        """
        path_suffix = []
        cx, cy = job.location
        direction = self._paths[cy][cx]

        while direction is not None:
            for i, sel_direction in enumerate(self._directions):
                if sel_direction == direction:
                    xoff, yoff = self._offsets[i]

            path_suffix.insert(0, (xoff, yoff))
            cx -= xoff
            cy -= yoff
            direction = self._paths[cy][cx]

        return self._shortest_path + path_suffix

    def run(self, limit=10, ignore_timeslice=False):
        """
        Continue a previously started job search.

        If this is not the correct timeslice, then nothing happens.

        Arguments:
            limit: the number of breadth descensions to try

        Returns:
            the found job as (x, y) or None if no job was found
        """
        exhausted_tiles = False

        if not ignore_timeslice \
           and self._stopwatch.measure(self._cookie) \
               % NUM_OF_TIMESLICES != self._timeslice:
            return

        while not exhausted_tiles and limit > 0:
            exhausted_tiles = True

            for y in range(self._stage.height):
                for x in range(self._stage.width):
                    if self._visited[y][x] \
                       and not self._staleness[y][x] \
                       and not tile_is_solid(
                                 self._stage.get_tile_at(x, y)):
                        # This is a non-solid tile, so
                        # check all paths leading out from it.
                        i = 0
                        for xoff, yoff in self._offsets:
                            ox = x + xoff
                            oy = y + yoff
                            if ox < 0 or ox >= self._stage.width \
                               or oy < 0 or oy >= self._stage.height:
                                pass
                            elif not self._visited[oy][ox]:
                                self._visited[oy][ox] = True
                                self._paths[oy][ox] = \
                                    self._directions[i]
                                exhausted_tiles = False
                                # Check if there is a job there.
                                for job in self._mine_jobs:
                                    if not job.reserved \
                                       and not job.done \
                                       and job.location[0] == ox \
                                       and job.location[1] == oy:
                                        self.busy = False
                                        return (job,
                                                self._traceback(job))
                            i += 1
                        self._staleness[y][x] = True
            limit -= 1

        if exhausted_tiles:
            self.busy = False

        # No job was found.
        return None