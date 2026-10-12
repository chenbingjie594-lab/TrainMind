package com.jiawa.service;

import com.jiawa.domain.ConfirmOrder;
import com.jiawa.dto.ConfirmOrderMQDto;
import com.jiawa.req.ConfirmOrderQueryReq;
import com.jiawa.req.ConfirmOrderDoReq;
import com.jiawa.resp.ConfirmOrderQueryResp;
import com.jiawa.resp.PageResp;
import jakarta.validation.Valid;

public interface ConfirmOrderService {
    void save(ConfirmOrderDoReq req);

    PageResp<ConfirmOrderQueryResp> queryList(ConfirmOrderQueryReq req);

    void delete(Long id);

    void doConfirm(@Valid ConfirmOrderMQDto dto);

    void sell(ConfirmOrder confirmOrder);

    Integer queryLineCount(Long id);
}