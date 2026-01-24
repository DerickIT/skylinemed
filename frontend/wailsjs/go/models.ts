export namespace core {
	
	export class AddressOption {
	    id: string;
	    text: string;
	
	    static createFrom(source: any = {}) {
	        return new AddressOption(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.id = source["id"];
	        this.text = source["text"];
	    }
	}
	export class Member {
	    id: string;
	    name: string;
	    certified: boolean;
	
	    static createFrom(source: any = {}) {
	        return new Member(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.id = source["id"];
	        this.name = source["name"];
	        this.certified = source["certified"];
	    }
	}
	export class SubmitOrderResult {
	    success: boolean;
	    status: boolean;
	    msg: string;
	    url?: string;
	
	    static createFrom(source: any = {}) {
	        return new SubmitOrderResult(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.success = source["success"];
	        this.status = source["status"];
	        this.msg = source["msg"];
	        this.url = source["url"];
	    }
	}
	export class TimeSlot {
	    name: string;
	    value: string;
	
	    static createFrom(source: any = {}) {
	        return new TimeSlot(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.name = source["name"];
	        this.value = source["value"];
	    }
	}
	export class TicketDetail {
	    times: TimeSlot[];
	    time_slots: TimeSlot[];
	    sch_data: string;
	    detlid_realtime: string;
	    level_code: string;
	    sch_date: string;
	    order_no: string;
	    disease_content: string;
	    disease_input: string;
	    is_hot: string;
	    hisMemId: string;
	    addressId: string;
	    address: string;
	    addresses: AddressOption[];
	
	    static createFrom(source: any = {}) {
	        return new TicketDetail(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.times = this.convertValues(source["times"], TimeSlot);
	        this.time_slots = this.convertValues(source["time_slots"], TimeSlot);
	        this.sch_data = source["sch_data"];
	        this.detlid_realtime = source["detlid_realtime"];
	        this.level_code = source["level_code"];
	        this.sch_date = source["sch_date"];
	        this.order_no = source["order_no"];
	        this.disease_content = source["disease_content"];
	        this.disease_input = source["disease_input"];
	        this.is_hot = source["is_hot"];
	        this.hisMemId = source["hisMemId"];
	        this.addressId = source["addressId"];
	        this.address = source["address"];
	        this.addresses = this.convertValues(source["addresses"], AddressOption);
	    }
	
		convertValues(a: any, classs: any, asMap: boolean = false): any {
		    if (!a) {
		        return a;
		    }
		    if (a.slice && a.map) {
		        return (a as any[]).map(elem => this.convertValues(elem, classs));
		    } else if ("object" === typeof a) {
		        if (asMap) {
		            for (const key of Object.keys(a)) {
		                a[key] = new classs(a[key]);
		            }
		            return a;
		        }
		        return new classs(a);
		    }
		    return a;
		}
	}

}

export namespace main {
	
	export class LogEntry {
	    time: string;
	    level: string;
	    message: string;
	
	    static createFrom(source: any = {}) {
	        return new LogEntry(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.time = source["time"];
	        this.level = source["level"];
	        this.message = source["message"];
	    }
	}

}

