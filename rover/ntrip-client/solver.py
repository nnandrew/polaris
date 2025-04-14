from queue import Queue
from threading import Event, Thread
from time import sleep
from pygnssutils import GNSSNTRIPClient
from pprint import pprint
import ecef_solver
import gnss_reader
import msm_parser

"""

Mount Point AUS_LOFT_GNSS 
    Distance: 7km
    Messages: https://www.use-snip.com/kb/knowledge-base/rtcm-3-message-list/
        RTCM 1074 GPS MSM4
        RTCM 1084 GLONASS MSM4
        RTCM 1094 Galileo MSM4
        RTCM 1124 BeiDou MSM4
MSM4 Components: https://www.tersus-gnss.com/tech_blog/new-additions-in-rtcm3-and-What-is-msm
    Full GPS Pseudoranges, Phaseranges, Carrier-to-Noise Ratio
"""

def ntripthread(outqueue: Queue, stopevent: Event):

    gnc = GNSSNTRIPClient()
    gnc.run(
        # Required Configuration
        server="rtk2go.com",
        port=2101,
        https=0,
        mountpoint="AUS_LOFT_GNSS",
        datatype="RTCM",
        ntripuser="andrewvnguyen@utexas.edu",
        ntrippassword="none",
        output=outqueue,
        # DGPS Configuration (unused)
        ggainterval=-1,
        ggamode=1,  # fixed rover reference coordinates
        reflat=0.0,
        reflon=0.0,
        refalt=0.0,
        refsep=0.0,
    )
    while not stopevent.is_set():
        sleep(3)
        
def datathread(outqueue: Queue, stopevent: Event):

    while not stopevent.is_set():
        while not outqueue.empty():
            raw, parsed = outqueue.get()
            # if parsed.ismsm:
            if parsed.identity == "1074":
                rtcm_metadata, rtcm_sats = msm_parser.parse(parsed)
                pprint(rtcm_metadata)
                pprint(rtcm_sats)
                rover_ecef = gnss_reader.getECEF()
                rover_sats = gnss_reader.getSatelliteInfo()
                # pprint(rover_sats)
                calculated_ecef = ecef_solver.solve(rover_ecef, rover_sats, rtcm_metadata, rtcm_sats)
                pprint(rover_ecef)
                pprint(calculated_ecef)
            outqueue.task_done()
        sleep(1)
        
def main():
    
    # initialize structures
    outqueue = Queue()
    stopevent = Event()

    # define the threads which will run in the background until terminated by user
    dt = Thread(
        target=datathread, 
        args=(outqueue, stopevent), 
        daemon=True
    )
    nt = Thread(
        target=ntripthread, 
        args=(outqueue, stopevent), 
        daemon=True
    )
    
    # start the threads
    dt.start()
    nt.start()

    print("NTRIP client and processor threads started - press CTRL-C to terminate...")
    
    # Idle Parent Thread
    try:
        while True:
            sleep(3)
    except KeyboardInterrupt:
        # stop the threads
        stopevent.set()
        print("NTRIP client terminated by user, waiting for data processing to complete...")

    # wait for final queued tasks to complete
    nt.join()
    dt.join()

    print(f"Data processing complete.")

if __name__ == "__main__":
    main()