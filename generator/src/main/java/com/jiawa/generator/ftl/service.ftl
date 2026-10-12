package com.jiawa.service;

import com.jiawa.req.PassengerQueryReq;
import com.jiawa.req.PassengerSaveReq;
import com.jiawa.resp.PageResp;
import com.jiawa.resp.PassengerQueryResp;

public interface ${Domain}Service {
    void save(${Domain}SaveReq req);

    PageResp<${Domain}QueryResp> queryList(${Domain}QueryReq req);

    void delete(Long id);
}