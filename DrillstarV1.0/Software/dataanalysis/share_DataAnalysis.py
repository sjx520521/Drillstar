
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSize


class ShareInfo:

    app = None

    sql_isConnect = False
    sql_Tables = []
    DBNAME = "oilfile"
    DBHOST = "localhost"
    DBPORT = "3306"
    DBUSER = "root"
    DBPASS = "119aab19abba91"


    """时域特征"""
    features = ['参数','最大值','最小值','峰值','平均值','方差','标准差','均方根','峭度','裕度','偏度','波形因子','峰度因子','脉冲因子','裕度因子']
    features_func = {'最大值': lambda data: data.max(),
                     '最小值': lambda data: data.min(),
                     '峰值':   lambda data: data.max(),
                     '平均值': lambda data: data.mean(),
                     '方差':   lambda data: data.var(),
                     '标准差': lambda data: data.std(),
                     '均方根': lambda data: data.var(),
                     # '峭度':   lambda data: data.skew(),
                     # '裕度':   lambda data: data.kurtosis(),
                     # '偏度':   lambda data: data.skew(),
                     # '波形因子':   lambda data: data.kurt() / data.std(),
                     # '峰度因子':   lambda data: data.kurt() / data.mean(),
                     # '脉冲因子':   lambda data: data.kurt() / data.max(),
                     # '裕度因子':   lambda data: data.kurt() / data.var(),
                     }






