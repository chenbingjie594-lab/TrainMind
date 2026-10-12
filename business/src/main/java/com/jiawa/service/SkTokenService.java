package com.jiawa.service;

import com.jiawa.req.SkTokenQueryReq;
import com.jiawa.req.SkTokenSaveReq;
import com.jiawa.resp.PageResp;
import com.jiawa.resp.SkTokenQueryResp;

public interface SkTokenService {
    void save(SkTokenSaveReq req);

    PageResp<SkTokenQueryResp> queryList(SkTokenQueryReq req);

    void delete(Long id);
}