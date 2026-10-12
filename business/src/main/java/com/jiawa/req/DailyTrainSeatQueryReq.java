package com.jiawa.req;

import lombok.Data;

@Data
public class DailyTrainSeatQueryReq extends PageReq {
    public String trainCode;
}
