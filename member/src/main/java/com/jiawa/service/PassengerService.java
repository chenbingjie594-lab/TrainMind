package com.jiawa.service;

import com.jiawa.req.PassengerQueryReq;
import com.jiawa.req.PassengerSaveReq;
import com.jiawa.resp.PageResp;
import com.jiawa.resp.PassengerQueryResp;

import java.util.List;

public interface PassengerService {
    void save(PassengerSaveReq req);

    PageResp<PassengerQueryResp> queryList(PassengerQueryReq req);

    void delete(Long id);

    List<PassengerQueryResp> queryMine();
}