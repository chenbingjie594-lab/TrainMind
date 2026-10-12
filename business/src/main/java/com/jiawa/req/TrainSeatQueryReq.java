package com.jiawa.req;

import lombok.Data;

@Data
public class TrainSeatQueryReq extends PageReq {
    private String trainCode;
}
