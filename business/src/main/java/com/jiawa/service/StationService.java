package com.jiawa.service;

import com.jiawa.req.StationQueryReq;
import com.jiawa.req.StationSaveReq;
import com.jiawa.resp.PageResp;
import com.jiawa.resp.StationQueryResp;

import java.util.List;

public interface StationService {
    void save(StationSaveReq req);

    PageResp<StationQueryResp> queryList(StationQueryReq req);

    void delete(Long id);

    List<StationQueryResp> queryAll();
}