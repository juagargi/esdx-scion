from concurrent.futures import ThreadPoolExecutor
from util.standalone import run_django
import time


class Runner:
    def __init__(
        self,
        service_address: str,  # e.g. "localhost:50051"
        seller_fcn,  # the function to execute per seller
        sellers_data,  # list of len(sellers) tuples, each with the parameters for seller_fcn
        buyer_fcn,  # the function to execute per buyer
        buyers_data,  # list of len(buyers) tuples, each with the parameters for buyer_fcn
        ):
        """
        data_sellers: list of len(sellers) elements, each consisting on the arguments to the sellers function
        """
        self.service_address = service_address
        self.seller_fcn = seller_fcn
        self.sellers_data = sellers_data
        self.buyer_fcn = buyer_fcn
        self.buyers_data = buyers_data

    def run(self):
        django = run_django()
        tasks = []
        with ThreadPoolExecutor() as executor:
            # launch sellers
            for args in self.sellers_data:
                tasks.append(executor.submit(self.seller_fcn, *args))
            time.sleep(1)  # let the sellers work for a while

            # launch buyers
            for args in self.buyers_data:
                tasks.append(executor.submit(self.buyer_fcn, *args))

        res = 0
        for t in tasks:
            result = t.result()
            if result != 0:
                res = 1
        try:
            django.terminate()
        finally:
            django.kill()
        return res
