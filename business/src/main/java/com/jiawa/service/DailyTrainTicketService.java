package com.jiawa.service;

import com.jiawa.domain.DailyTrain;
import com.jiawa.domain.DailyTrainTicket;
import com.jiawa.req.DailyTrainTicketQueryReq;
import com.jiawa.req.DailyTrainTicketSaveReq;
import com.jiawa.resp.DailyTrainTicketQueryResp;
import com.jiawa.resp.PageResp;

import java.util.Date;

public interface DailyTrainTicketService {
    void save(DailyTrainTicketSaveReq req);

    PageResp<DailyTrainTicketQueryResp> queryList(DailyTrainTicketQueryReq req);

    void delete(Long id);

    void genDaily(DailyTrain dailyTrain, Date date, String trainCode);

    DailyTrainTicket selectByUnique(Date date, String trainCode, String start, String end);
}