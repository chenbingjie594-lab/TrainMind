package com.jiawa.service;

import com.jiawa.req.MemberTicketReq;
import com.jiawa.req.TicketQueryReq;
import com.jiawa.resp.PageResp;
import com.jiawa.resp.TicketQueryResp;

public interface TicketService {
    void save(MemberTicketReq req) throws Exception;

    PageResp<TicketQueryResp> queryList(TicketQueryReq req);

    void delete(Long id);
}