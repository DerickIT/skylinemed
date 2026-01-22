#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
医生过滤器 - 黑白名单与职称筛选
支持: 黑名单、白名单、职称过滤、费用过滤
"""
from typing import List, Dict, Set, Optional
from dataclasses import dataclass, field


@dataclass
class DoctorFilter:
    """
    医生过滤器
    
    使用示例:
        filter = DoctorFilter()
        filter.add_blacklist("12345")  # 排除特定医生
        filter.set_titles(["主任医师", "副主任医师"])  # 只要高级职称
        filter.max_fee = 50.0  # 挂号费上限
        
        filtered = filter.filter(doctors)
    """
    
    # 黑名单 (排除)
    blacklist: Set[str] = field(default_factory=set)
    
    # 白名单 (优先，如果非空则只匹配白名单)
    whitelist: Set[str] = field(default_factory=set)
    
    # 职称过滤
    titles: List[str] = field(default_factory=list)
    
    # 费用上限
    max_fee: Optional[float] = None
    
    # 最小余号数
    min_left_num: int = 1
    
    # 时段类型 (am/pm)
    time_types: List[str] = field(default_factory=lambda: ['am', 'pm'])
    
    def add_blacklist(self, doctor_id: str):
        """添加到黑名单"""
        self.blacklist.add(str(doctor_id))
    
    def remove_blacklist(self, doctor_id: str):
        """从黑名单移除"""
        self.blacklist.discard(str(doctor_id))
    
    def add_whitelist(self, doctor_id: str):
        """添加到白名单"""
        self.whitelist.add(str(doctor_id))
    
    def remove_whitelist(self, doctor_id: str):
        """从白名单移除"""
        self.whitelist.discard(str(doctor_id))
    
    def set_titles(self, titles: List[str]):
        """设置职称过滤"""
        self.titles = titles
    
    def filter(self, doctors: List[Dict]) -> List[Dict]:
        """
        过滤医生列表
        
        Args:
            doctors: 医生列表
        
        Returns:
            过滤后的医生列表
        """
        result = []
        
        for doc in doctors:
            doc_id = str(doc.get('doctor_id', ''))
            
            # 白名单模式
            if self.whitelist:
                if doc_id not in self.whitelist:
                    continue
            
            # 黑名单检查
            if doc_id in self.blacklist:
                continue
            
            # 职称过滤
            if self.titles:
                doc_title = doc.get('doctor_title', '') or doc.get('title', '')
                if not any(t in doc_title for t in self.titles):
                    continue
            
            # 费用过滤
            if self.max_fee is not None:
                try:
                    fee = float(doc.get('reg_fee', 0) or doc.get('fee', 0) or 0)
                    if fee > self.max_fee:
                        continue
                except (ValueError, TypeError):
                    pass
            
            # 余号过滤
            left_num = doc.get('total_left_num', 0)
            if isinstance(left_num, str):
                try:
                    left_num = int(left_num)
                except:
                    left_num = 0
            
            if left_num < self.min_left_num:
                continue
            
            # 时段过滤 (检查 schedules)
            if self.time_types:
                schedules = doc.get('schedules', [])
                valid_schedules = [
                    s for s in schedules 
                    if s.get('time_type', '') in self.time_types
                ]
                if not valid_schedules:
                    continue
                doc['schedules'] = valid_schedules
            
            result.append(doc)
        
        return result
    
    def to_dict(self) -> Dict:
        """转换为字典 (用于保存)"""
        return {
            'blacklist': list(self.blacklist),
            'whitelist': list(self.whitelist),
            'titles': self.titles,
            'max_fee': self.max_fee,
            'min_left_num': self.min_left_num,
            'time_types': self.time_types,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DoctorFilter':
        """从字典创建"""
        return cls(
            blacklist=set(data.get('blacklist', [])),
            whitelist=set(data.get('whitelist', [])),
            titles=data.get('titles', []),
            max_fee=data.get('max_fee'),
            min_left_num=data.get('min_left_num', 1),
            time_types=data.get('time_types', ['am', 'pm']),
        )


class FilterPresets:
    """预设过滤器"""
    
    @staticmethod
    def senior_doctors() -> DoctorFilter:
        """只要高级职称"""
        f = DoctorFilter()
        f.set_titles(["主任医师", "副主任医师"])
        return f
    
    @staticmethod
    def junior_doctors() -> DoctorFilter:
        """只要普通职称 (适合不急的复诊)"""
        f = DoctorFilter()
        f.set_titles(["主治医师", "住院医师"])
        return f
    
    @staticmethod
    def morning_only() -> DoctorFilter:
        """只要上午号"""
        f = DoctorFilter()
        f.time_types = ['am']
        return f
    
    @staticmethod
    def afternoon_only() -> DoctorFilter:
        """只要下午号"""
        f = DoctorFilter()
        f.time_types = ['pm']
        return f
    
    @staticmethod
    def budget(max_fee: float = 50.0) -> DoctorFilter:
        """限制费用"""
        f = DoctorFilter()
        f.max_fee = max_fee
        return f


def filter_doctors(doctors: List[Dict], config: Dict) -> List[Dict]:
    """
    便捷函数: 根据配置过滤医生
    
    Args:
        doctors: 医生列表
        config: 包含过滤配置的字典
    
    Returns:
        过滤后的医生列表
    """
    filter_config = config.get('filter', {})
    if not filter_config:
        # 兼容旧配置: 使用 doctor_ids 作为白名单
        doctor_ids = config.get('doctor_ids', [])
        if doctor_ids:
            filter_config = {'whitelist': doctor_ids}
    
    if not filter_config:
        return doctors
    
    doc_filter = DoctorFilter.from_dict(filter_config)
    return doc_filter.filter(doctors)


if __name__ == "__main__":
    # 测试过滤器
    doctors = [
        {'doctor_id': '1', 'doctor_name': '张主任', 'doctor_title': '主任医师', 'total_left_num': 5, 'reg_fee': 100},
        {'doctor_id': '2', 'doctor_name': '李副主任', 'doctor_title': '副主任医师', 'total_left_num': 3, 'reg_fee': 80},
        {'doctor_id': '3', 'doctor_name': '王医生', 'doctor_title': '主治医师', 'total_left_num': 10, 'reg_fee': 30},
        {'doctor_id': '4', 'doctor_name': '刘实习', 'doctor_title': '住院医师', 'total_left_num': 20, 'reg_fee': 20},
    ]
    
    print("=== 原始列表 ===")
    for d in doctors:
        print(f"  {d['doctor_name']} - {d['doctor_title']} - ¥{d['reg_fee']}")
    
    print("\n=== 高级职称过滤 ===")
    f = FilterPresets.senior_doctors()
    for d in f.filter(doctors):
        print(f"  {d['doctor_name']} - {d['doctor_title']}")
    
    print("\n=== 费用 ≤50 过滤 ===")
    f = FilterPresets.budget(50)
    for d in f.filter(doctors):
        print(f"  {d['doctor_name']} - ¥{d['reg_fee']}")
    
    print("\n=== 黑名单排除 ===")
    f = DoctorFilter()
    f.add_blacklist('4')  # 排除刘实习
    for d in f.filter(doctors):
        print(f"  {d['doctor_name']}")
