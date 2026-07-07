"""
OTA 业务模板模块
提供机票、酒店、火车票等业务的配置化模板
"""
from .base_template import BaseBusinessTemplate
from .flight_template import FlightTemplate
from .hotel_template import HotelTemplate
from .train_template import TrainTemplate

# 模板注册表
TEMPLATE_REGISTRY = {
    "flight": FlightTemplate,
    "hotel": HotelTemplate,
    "train": TrainTemplate,
}


def get_template(product_type: str) -> BaseBusinessTemplate:
    """根据业务类型获取对应模板"""
    template_class = TEMPLATE_REGISTRY.get(product_type)
    if template_class:
        return template_class()
    return BaseBusinessTemplate()


__all__ = [
    "BaseBusinessTemplate",
    "FlightTemplate",
    "HotelTemplate",
    "TrainTemplate",
    "TEMPLATE_REGISTRY",
    "get_template",
]