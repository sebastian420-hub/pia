from pia.sensors.providers.caltrans import Caltrans
from pia.sensors.providers.fi_digitraffic import FinlandDigitraffic
from pia.sensors.providers.hk_td import HongKongTD
from pia.sensors.providers.nyc_dot import NYCDOT
from pia.sensors.providers.nzta import NZTA
from pia.sensors.providers.sg_lta import SingaporeLTA
from pia.sensors.providers.tfl import TfLJamCams
from pia.sensors.providers.toronto import Toronto

ALL_PROVIDERS = [HongKongTD, TfLJamCams, SingaporeLTA, NZTA, FinlandDigitraffic, Toronto, NYCDOT, Caltrans]
PROVIDERS_BY_ID = {p.provider_id: p for p in ALL_PROVIDERS}
