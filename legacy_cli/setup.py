#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置预选脚本 - 交互式选择参数并保存到 config.json
"""
import json
import os
from client import HealthClient

def select_from_list(items, display_func=None, multi=False):
    """从列表中选择项目"""
    if not items:
        return None if not multi else []
    
    for i, item in enumerate(items):
        if display_func:
            print(f"[{i}] {display_func(item)}")
        else:
            print(f"[{i}] {item}")
    
    if multi:
        print("\n提示: 输入多个序号用逗号分隔 (如: 0,1,2)，直接回车选择全部")
        choice = input(f"请输入序号: ").strip()
        if not choice:
            return items
        try:
            indices = [int(x.strip()) for x in choice.split(',')]
            return [items[i] for i in indices if 0 <= i < len(items)]
        except:
            return []
    else:
        while True:
            choice = input(f"请输入序号 (0-{len(items)-1}): ").strip()
            try:
                idx = int(choice)
                if 0 <= idx < len(items):
                    return items[idx]
            except:
                pass
            print("[-] 输入无效，请重新输入")

def filter_list(items, key_func, prompt):
    """过滤列表"""
    keyword = input(prompt).strip()
    if not keyword:
        return items
    return [item for item in items if keyword.lower() in key_func(item).lower()]

def setup():
    print("=== 91160 抢号配置向导 ===\n")
    
    client = HealthClient()
    if not client.login():
        print("[-] 登录失败")
        return
    
    config = {}
    
    # 1. 首先选择就诊人 (登录后立即获取，session 状态最佳)
    print("\n[*] 正在获取就诊人列表...")
    
    # 预热：先访问 user 子域首页激活跨子域 session
    try:
        client.session.get("https://user.91160.com/user/index.html", timeout=5)
    except:
        pass
    
    members = client.get_members()
    if not members:
        print("[-] 获取就诊人列表失败，请确保已登录并添加了就诊人")
        return
    
    member = select_from_list(members, lambda x: f"{x['name']} ({'已认证' if x['certified'] else '未认证'})")
    if not member:
        return
    
    config['member_id'] = str(member['id'])
    config['member_name'] = member['name']
    print(f"[+] 已选择就诊人: {member['name']}")
    
    # 2. 选择城市
    print("\n[*] 加载城市列表...")
    cities = []
    cities_file = os.path.join(os.path.dirname(__file__), 'cities.json')
    try:
        with open(cities_file, 'r', encoding='utf-8') as f:
            cities = json.load(f)
    except Exception as e:
        print(f"[-] 城市列表加载失败: {e}, 使用默认深圳")
        cities = [{'name': '深圳', 'cityId': '5'}]

    city_filter = input("请输入城市名称关键字 (直接回车显示全部): ").strip()
    if city_filter:
        cities = [c for c in cities if city_filter in c.get('name', '')]

    if not cities:
        print("[-] 未找到匹配的城市")
        return
    
    selected_city = select_from_list(cities, lambda x: x['name'])
    if not selected_city:
        return
    city_id = selected_city.get('cityId', '5')
    config['city_id'] = city_id
    config['city_name'] = selected_city['name']
    print(f"[+] 已选择城市: {selected_city['name']} (ID: {city_id})")
    
    # 3. 选择医院
    print("\n[*] 正在获取医院列表...")
    hospitals = client.get_hospitals_by_city(city_id)
    if not hospitals:
        print("[-] 获取医院列表失败")
        return
    
    hospital_name_keys = ['unit_name', 'name']
    hospitals = filter_list(
        hospitals,
        lambda x: next((x[k] for k in hospital_name_keys if k in x), ""),
        "请输入医院关键字进行过滤 (直接回车显示全部): "
    )
    
    hospital = select_from_list(
        hospitals,
        lambda x: x.get('unit_name') or x.get('name', '')
    )
    if not hospital:
        return
    
    config['unit_id'] = str(hospital.get('unit_id', hospital.get('id', '')))
    config['unit_name'] = hospital.get('unit_name', hospital.get('name', ''))
    print(f"[+] 已选择: {config['unit_name']}")
    
    # 4. 选择科室
    print("\n[*] 正在获取科室列表...")
    dep_categories = client.get_deps_by_unit(config['unit_id'])
    
    # 展平科室结构 (与 main.py 保持一致)
    departments = []
    if isinstance(dep_categories, list):
        for cat in dep_categories:
            if 'childs' in cat and cat['childs']:
                departments.extend(cat['childs'])
            elif 'dep_id' in cat:
                departments.append(cat)
    
    if not departments:
        print("[-] 获取科室列表失败")
        return
    
    departments = filter_list(departments, lambda x: x.get('dep_name', x.get('name', '')),
                             "请输入科室关键字进行过滤 (直接回车显示全部): ")
    
    department = select_from_list(
        departments,
        lambda x: x.get('dep_name') or x.get('name', '')
    )
    if not department:
        return
    
    config['dep_id'] = str(department.get('dep_id', department.get('id', '')))
    config['dep_name'] = department.get('dep_name', department.get('name', ''))
    print(f"[+] 已选择: {config['dep_name']}")
    
    # 5. 选择目标日期
    print("\n[*] 请选择目标日期 (可多选):")
    import datetime
    dates = []
    today = datetime.date.today()
    for i in range(7):
        d = today + datetime.timedelta(days=i)
        dates.append(d.strftime("%Y-%m-%d"))
    
    selected_dates = select_from_list(dates, multi=True)
    if not selected_dates:
        print("[-] 未选择日期")
        return
    
    config['target_dates'] = selected_dates
    print(f"[+] 已选择日期: {', '.join(selected_dates)}")
    
    # 6. 选择医生 (可选)
    print("\n[*] 正在获取医生列表...")
    docs = client.get_schedule(config['unit_id'], config['dep_id'], selected_dates[0])
    
    if docs:
        print("\n是否指定特定医生? (不指定则抢任意有号医生)")
        choice = input("输入 y 指定医生，直接回车跳过: ").strip().lower()
        if choice == 'y':
            selected_docs = select_from_list(
                docs, 
                lambda x: f"{x.get('doctor_name')} - {x.get('expert', '')[:30]}...",
                multi=True
            )
            if selected_docs:
                config['doctor_ids'] = [str(d['doctor_id']) for d in selected_docs]
                config['doctor_names'] = [d['doctor_name'] for d in selected_docs]
                print(f"[+] 已选择医生: {', '.join(config['doctor_names'])}")
    
    if 'doctor_ids' not in config:
        config['doctor_ids'] = []
        config['doctor_names'] = []
        print("[*] 未指定医生，将抢任意有号医生")
    
    # 7. 选择时段类型
    print("\n[*] 请选择目标时段:")
    print("[0] 上午 + 下午 (推荐)")
    print("[1] 仅上午")
    print("[2] 仅下午")
    choice = input("请输入序号 [默认0]: ").strip()
    if choice == '1':
        config['time_types'] = ['am']
    elif choice == '2':
        config['time_types'] = ['pm']
    else:
        config['time_types'] = ['am', 'pm']
    
    # 8. 定时设置 (可选)
    print("\n[*] 定时设置 (医院一般 00:00 或 06:00 放号)")
    start_time = input("输入开始抢号时间 (格式 HH:MM:SS，直接回车立即开始): ").strip()
    config['start_time'] = start_time
    
    # 9. 其他设置
    config['retry_interval'] = 0.3  # 重试间隔 (秒)
    config['max_retries'] = 0  # 0 表示无限重试
    config['preferred_hours'] = []  # 优先时段
    
    # 保存配置
    config_path = "config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*50}")
    print("[SUCCESS] 配置已保存到 config.json")
    print(f"{'='*50}")
    print("\n配置摘要:")
    print(f"  城市: {config.get('city_name', '未知')}")
    print(f"  医院: {config['unit_name']}")
    print(f"  科室: {config['dep_name']}")
    print(f"  日期: {', '.join(config['target_dates'])}")
    print(f"  医生: {', '.join(config['doctor_names']) or '任意'}")
    print(f"  就诊人: {config['member_name']}")
    print(f"  定时: {config['start_time'] or '立即开始'}")
    print(f"\n运行抢号命令: python grab.py")

if __name__ == "__main__":
    setup()
