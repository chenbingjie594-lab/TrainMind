package com.jiawa.feign;

import com.jiawa.req.MemberTicketReq;
import com.jiawa.resp.CommonResp;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

// @FeignClient("member")
@FeignClient(name = "member", url = "http://127.0.0.1:8001/member")
public interface MemberFeign {

    @PostMapping("/feign/ticket/save")
    CommonResp<Object> save(@RequestBody MemberTicketReq req);

}
