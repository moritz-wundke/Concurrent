from dnacurve import CurvedDNA
import time
if __name__ == '__main__':
    start = time.time()
    result = CurvedDNA("ATGCAAATTG"*1000, "trifonov", name="Example", maxlen=1024*1024)
    ellapsed = time.time() - start
    print(result)
    print("In {ellapsed} seconds".format(ellapsed=ellapsed))
